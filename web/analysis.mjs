export function csv(rows,columns) {
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return '\uFEFF'+[columns.map(c=>quote(c.label)).join(','),...rows.map(r=>columns.map(c=>quote(r[c.key])).join(','))].join('\r\n');
}
