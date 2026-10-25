// Spreadsheet authoring uses the bundled @oai/artifact-tool runtime, not repo dependencies.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
process.on('uncaughtException', error => { console.error(error.message); process.exitCode = 1; });

const [template, planPath, output, runtimeDirectory, preparedTemplate] = process.argv.slice(2);
if (!runtimeDirectory) throw new Error('Usage: node export_book2.mjs template.xlsx plan.json authored.xlsx bundled-node-directory');
if (path.resolve(output) === path.resolve(template)) throw new Error('Output must differ from template');
const runtime = createRequire(path.join(path.resolve(runtimeDirectory), 'package.json'));
const { FileBlob, SpreadsheetFile } = await import(pathToFileURL(runtime.resolve('@oai/artifact-tool')));
const plan = JSON.parse(await fs.readFile(planPath, 'utf8'));
const bytes = await fs.readFile(template);
if (createHash('sha256').update(bytes).digest('hex') !== plan.template_sha256) throw new Error('Template checksum mismatch');
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(preparedTemplate ?? template));
for (const spec of plan.sheets) {
  const sheet = wb.worksheets.getItem(spec.name);
  for (const range of spec.unmerge ?? []) sheet.getRange(range).unmerge();
  for (const range of spec.clear ?? []) sheet.getRange(range).clear({applyTo:'contents'});
  // Clear full sample formula groups before copying empty formatted cells.
  for (const item of spec.style_copies ?? []) sheet.getRange(item.target).copyFrom(sheet.getRange(item.source), 'all');
  for (const range of spec.merges ?? []) sheet.mergeCells(range);
  for (const item of spec.values ?? []) {
    sheet.getRange(item.range).values = item.values.map(row => row.map(v => typeof v === 'string' && v.startsWith('=') ? "'" + v : v));
  }
  for (const item of spec.formulas ?? []) sheet.getRange(item.range).formulas = item.formulas;
  for (const item of spec.column_widths ?? []) sheet.getRange(item.range).format.columnWidth = item.width;
  for (const item of spec.row_heights ?? []) sheet.getRange(item.range).format.rowHeight = item.height;
  for (const item of spec.number_formats ?? []) sheet.getRange(item.range).setNumberFormat(item.format);
  sheet.freezePanes.freezeRows(5);
}
wb.recalculate();
const inspection = await wb.inspect({kind:'formula',maxChars:3000,options:{maxResults:100}});
// Some bundled releases return other record kinds despite the inspect filter.
// Keep only formula inventory; cached error cells are checked by the finisher.
const formulas = inspection.ndjson.split('\n').filter(Boolean).map(line => JSON.parse(line)).filter(item => item.kind === 'formula');
await fs.mkdir(path.dirname(output), {recursive:true});
await fs.writeFile(output + '.formulas.ndjson', formulas.map(item => JSON.stringify(item)).join('\n') + '\n');
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(output);
for (const [index,spec] of plan.sheets.entries()) {
  const range = index === 0 ? spec.print_area : `A1:P${Math.min(Number(spec.print_area.match(/\d+$/)[0]),30)}`;
  const image = await wb.render({sheetName:spec.name,range,scale:1.3,format:'png'});
  await fs.writeFile(output + `.sheet${index+1}.png`, new Uint8Array(await image.arrayBuffer()));
}
console.log(JSON.stringify({authored:output,preview_sheets:plan.sheets.length,formula_inventory_count:formulas.length}));
