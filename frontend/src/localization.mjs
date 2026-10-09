import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { fa } from './locales/fa.mjs';

export const LANGUAGE_KEY='demandlab.interfaceLanguage';
export const languages=['en','fa'];
export function storedLanguage(storage) {
  try { const value=storage?.getItem(LANGUAGE_KEY);return languages.includes(value)?value:'en'; }
  catch { return 'en'; }
}
export const i18n=i18next.createInstance();
i18n.use(initReactI18next).init({
  lng:storedLanguage(typeof localStorage==='undefined'?null:localStorage),
  fallbackLng:'en',supportedLngs:languages,initAsync:false,
  keySeparator:false,nsSeparator:false,
  resources:{en:{translation:{...Object.fromEntries(Object.keys(fa).map(key=>[key,key])),
    pageProgress:'Page {{page}} of {{total}}',stepProgress:'Step {{step}} of {{total}}'}},fa:{translation:fa}},
  interpolation:{escapeValue:false},react:{useSuspense:false},
});
// Only authored UI labels use this function. Never translate business identifiers.
export const t=(key,options={})=>i18n.t(key,{defaultValue:key,...options});
export const pluralSuffix=count=>i18n.language==='fa'||count===1?'':'s';
export function interfaceDirection(language=i18n.language){return language==='fa'?'rtl':'ltr';}
export async function changeInterfaceLanguage(language,storage) {
  if(!languages.includes(language))throw new Error('Unsupported interface language.');
  await i18n.changeLanguage(language);
  try{storage?.setItem(LANGUAGE_KEY,language);}catch{/* A blocked preference store must not break the interface. */}
}
export function applyInterfaceLanguage(document,language=i18n.language){
  document.documentElement.lang=language;
  document.documentElement.dir=interfaceDirection(language);
}
export function unitLabel(unit){
  const labels={units:'Units',tonnes:'Tonnes',kg:'Kg',litres:'Litres',hours:'Hours'};
  return labels[unit]?t(labels[unit]):unit;
}
