export function score(rows) {
  if (!rows.length) return {mae:null,mape:null,count:0,percentageCount:0};
  let absolute=0,percentage=0,percentageCount=0;
  for (const r of rows) {
    const error=Math.abs(r.actual-r.prediction); absolute+=error;
    if (r.actual!==0) {percentage+=error/Math.abs(r.actual);percentageCount++;}
  }
  return {mae:absolute/rows.length,mape:percentageCount?percentage/percentageCount*100:null,count:rows.length,percentageCount};
}
export function dayRows(profile,day) {return profile.rows.filter(r=>r.time.slice(0,10)===day);}
export function validateProfiles(data) {
  if (!data.profiles?.prophet_h1) throw new Error('Chưa có dữ liệu giao diện mới. Chạy python -m ems.web.prepare_dashboard.');
  for (const p of Object.values(data.profiles)) {
    if (!Array.isArray(p.rows)||!p.rows.length||![1,24].includes(p.horizon)) throw new Error('Kết quả dự báo không hợp lệ.');
    let previous;
    for (const r of p.rows) {
      const t=Date.parse(r.time+'Z');
      if (!Number.isFinite(t)||(previous!==undefined&&t-previous!==3600000)||![r.actual,r.prediction].every(x=>Number.isFinite(x)&&x>=0)) throw new Error('Dữ liệu phải liên tục theo giờ và có giá trị hợp lệ.');
      if (p.horizon===24 && (r.time.slice(0,10)!==r.origin?.slice(0,10)||r.lead!==Number(r.time.slice(11,13))+1||Date.parse(r.cutoff+'Z')!==Date.parse(r.origin+'Z')-3600000)) throw new Error('Mốc phát hành dự báo 24 giờ không hợp lệ.');
      previous=t;
    }
  }
  return data;
}
export function visibleSeries(rows,horizon,cursor) {
  return rows.map((r,i)=>({...r,observed:i<cursor?r.actual:null,forecast:horizon===24||i<=cursor?r.prediction:null}));
}
