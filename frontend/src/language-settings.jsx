import React,{useEffect} from 'react';
import {useTranslation} from 'react-i18next';
import {i18n,t,changeInterfaceLanguage,applyInterfaceLanguage} from './localization.mjs';
import {Panel} from './ui-layout.jsx';

export function useInterfaceLanguage(){
  const {i18n:instance}=useTranslation();
  useEffect(()=>applyInterfaceLanguage(document,instance.language),[instance.language]);
  return instance.language;
}
export function LanguageSettings({ui}){
  const {Field,Pick}=ui;
  useTranslation();
  return <Panel title={t('Language & layout')}>
    <Field title={t('Interface language')} help={t('Display only. Your planning calendar, customer names, product codes and export files stay unchanged.')}>
      <Pick label={t('Interface language')} value={i18n.language}
        options={[["en","English"],["fa","فارسی"]]}
        onChange={language=>changeInterfaceLanguage(language,localStorage)}/>
    </Field>
  </Panel>;
}
export function LanguageSwitch(){
  const {i18n:instance}=useTranslation();
  return <button type="button" className="language-switch" dir="ltr"
    aria-label={t('Interface language')} title={t('Interface language')}
    onClick={()=>changeInterfaceLanguage(instance.language==='fa'?'en':'fa',localStorage)}>
    {instance.language==='fa'?'English':'فارسی'}
  </button>;
}
