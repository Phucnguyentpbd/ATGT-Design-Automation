using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using System.Diagnostics;
using System.Text.Json;

namespace AtgtInspection;

// Run only in an isolated Core Console. Opens a side database for read;
// never changes, saves or makes a source drawing active.
public class Inspect
{
    static double[] P(Point3d p) => [p.X, p.Y, p.Z];
    [CommandMethod("ATGTINSPECT", CommandFlags.Session)]
    public void Run()
    {
        string source = Environment.GetEnvironmentVariable("ATGT_INSPECT_SOURCE") ?? throw new InvalidOperationException("Missing source");
        string output = Environment.GetEnvironmentVariable("ATGT_INSPECT_OUTPUT") ?? throw new InvalidOperationException("Missing output");
        if (Path.GetFullPath(source).Equals(Path.GetFullPath(output), StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Output must differ from source");
        using var db = new Database(false, true);
        db.ReadDwgFile(source, FileOpenMode.OpenForReadAndAllShare, false, null);
        db.CloseInput(true);
        using var tr = db.TransactionManager.StartTransaction();
        var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
        var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);
        var counts = new Dictionary<string, int>();
        var rows = new List<object>();
        var errors = new List<object>();
        var watch = Stopwatch.StartNew();
        int scanned = 0; bool truncated = false;
        foreach (ObjectId id in ms)
        {
            if (watch.Elapsed.TotalSeconds > 20 || scanned >= 100000 || rows.Count >= 25000) { truncated = true; break; }
            scanned++;
            string type = id.ObjectClass.DxfName;
            counts[type] = counts.GetValueOrDefault(type) + 1;
            if (type is not ("TEXT" or "MTEXT" or "LEADER" or "MULTILEADER" or "INSERT" or "LWPOLYLINE" or "LINE" or "SOLID")) continue;
            try
            {
                var e = (Entity)tr.GetObject(id, OpenMode.ForRead);
                var row = new Dictionary<string, object?> { ["handle"] = e.Handle.ToString(), ["type"] = type, ["layer"] = e.Layer, ["color"] = e.ColorIndex, ["linetype"] = e.Linetype };
                if (e is DBText t) { row["text"] = t.TextString; row["position"] = P(t.Position); row["height"] = t.Height; row["rotation"] = t.Rotation; row["style"] = ((TextStyleTableRecord)tr.GetObject(t.TextStyleId, OpenMode.ForRead)).Name; }
                else if (e is MText mt) { row["text"] = mt.Contents; row["position"] = P(mt.Location); row["height"] = mt.TextHeight; row["rotation"] = mt.Rotation; row["style"] = ((TextStyleTableRecord)tr.GetObject(mt.TextStyleId, OpenMode.ForRead)).Name; }
                else if (e is Leader l) { row["vertices"] = Enumerable.Range(0, l.NumVertices).Select(i => P(l.VertexAt(i))).ToArray(); row["annotation"] = l.Annotation.IsNull ? null : l.Annotation.Handle.ToString(); row["arrow"] = l.HasArrowHead; row["dimstyle"] = l.DimensionStyleName; }
                else if (e is MLeader ml) { row["contentType"] = ml.ContentType.ToString(); row["arrowSize"] = ml.ArrowSize; row["scale"] = ml.Scale; row["style"] = ((MLeaderStyle)tr.GetObject(ml.MLeaderStyle, OpenMode.ForRead)).Name; if (ml.ContentType == ContentType.MTextContent) { using var text = ml.MText; row["text"] = text.Contents; row["position"] = P(text.Location); row["height"] = text.TextHeight; } row["leaders"] = ml.GetLeaderIndexes().Cast<int>().SelectMany(i => ml.GetLeaderLineIndexes(i).Cast<int>()).Select(i => new { index = i, first = P(ml.GetFirstVertex(i)), last = P(ml.GetLastVertex(i)) }).ToArray(); }
                else if (e is BlockReference b) { var def = (BlockTableRecord)tr.GetObject(b.BlockTableRecord, OpenMode.ForRead); row["name"] = def.Name; row["position"] = P(b.Position); row["rotation"] = b.Rotation; row["scale"] = new[] { b.ScaleFactors.X, b.ScaleFactors.Y, b.ScaleFactors.Z }; var attrs = new List<object>(); foreach (ObjectId a in b.AttributeCollection) { var at = (AttributeReference)tr.GetObject(a, OpenMode.ForRead); attrs.Add(new { tag = at.Tag, text = at.TextString, position = P(at.Position) }); } row["attributes"] = attrs; }
                else if (e is Polyline pl) { if (pl.NumberOfVertices > 12) continue; row["vertices"] = Enumerable.Range(0, pl.NumberOfVertices).Select(i => P(pl.GetPoint3dAt(i))).ToArray(); row["width"] = pl.ConstantWidth; row["closed"] = pl.Closed; }
                else if (e is Line ln) row["vertices"] = new[] { P(ln.StartPoint), P(ln.EndPoint) };
                else if (e is Solid so) row["vertices"] = Enumerable.Range(0, 4).Select(i => P(so.GetPointAt((short)i))).ToArray();
                rows.Add(row);
            }
            catch (System.Exception ex) { errors.Add(new { handle = id.Handle.ToString(), type, error = ex.Message }); }
        }
        File.WriteAllText(output, JsonSerializer.Serialize(new { source, units = db.Insunits.ToString(), scanned, truncated, counts, errors, entities = rows }));
        // No transaction commit or SaveAs. Dispose discards the side database.
    }
}
