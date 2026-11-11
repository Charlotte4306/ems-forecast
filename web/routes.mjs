export const screenPaths=Object.freeze({tongquan:'/overview',dubao:'/forecast',daily:'/daily-forecast',kehoach:'/fleet-plan',chiphi:'/scenario-costs',danhgia:'/model-evaluation',lichsu:'/history',caidat:'/settings'});
export function screenFromLocation(url){
  const legacy=url.hash?.slice(1);
  if(Object.hasOwn(screenPaths,legacy))return legacy;
  return Object.keys(screenPaths).find(key=>screenPaths[key]===url.pathname.replace(/\/$/,''))||'tongquan';
}
export function screenUrl(key,url){
  const result=new URL(url.href);result.pathname=screenPaths[key]||screenPaths.tongquan;result.hash='';
  const profile=result.searchParams.get('profile');if(profile)result.searchParams.set('profile',profile.replaceAll('_','-').toLowerCase());
  return result.pathname+result.search;
}
