'use client';
import {useSyncExternalStore} from 'react';
export type ThemePreference='light'|'dark'|'system';
declare global {interface Window {f01Theme?:{get:()=>ThemePreference;set:(value:ThemePreference)=>void}}}
function subscribe(update:()=>void){window.addEventListener('f01-theme-changed',update);return()=>window.removeEventListener('f01-theme-changed',update);}
function snapshot():ThemePreference{return window.f01Theme?.get()??'light';}
export function ThemeControl({account=false}:{account?:boolean}){
 const preference=useSyncExternalStore(subscribe,snapshot,()=>'light');
 return <label className={`theme-control ${account?'theme-account':''}`}><span aria-hidden="true" className="theme-symbol"><svg className="theme-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/></svg><svg className="theme-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z"/></svg></span><span className="sr-only">{account?'Account appearance':'Color theme'}</span><select data-f01-theme-control value={preference} onChange={event=>window.f01Theme?.set(event.target.value as ThemePreference)}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></label>;
}
