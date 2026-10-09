'use client';
import {useEffect,useRef,useState} from 'react';
import type {Project} from '@/lib/projects/contracts';
import {projectRequest} from '@/lib/projects/browser';
import {fixturePath,type Snapshot,type Version} from '@/lib/workspace/contracts';
import {isolatedPreviewPath} from '@/lib/workspace/preview-url';
export function ProjectCover({project}:{project:Project}){
 const ref=useRef<HTMLDivElement>(null),[version,setVersion]=useState<Version|null>(null);
 useEffect(()=>{if(project.lifecycle!=='live'||project.archived_at||!ref.current)return;const controller=new AbortController();const observer=new IntersectionObserver(entries=>{if(!entries.some(item=>item.isIntersecting))return;observer.disconnect();void projectRequest<Snapshot>(`/projects/${project.id}/workspace`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)setVersion(value.current_version);}).catch(()=>{});});observer.observe(ref.current);return()=>{observer.disconnect();controller.abort();};},[project.id,project.lifecycle,project.archived_at]);
 const descriptor=version?.preview_descriptor,path=descriptor?.kind==='isolated'?isolatedPreviewPath(descriptor.url,descriptor.expires_at):descriptor?.kind==='fixture'?fixturePath(descriptor):null;
 return <div className="project-cover" ref={ref}>{path?<><div className="project-cover-live" inert aria-hidden="true"><iframe src={path} title="Project preview cover" tabIndex={-1} sandbox="allow-scripts" referrerPolicy="no-referrer"/></div><span className="project-cover-label">{version?.mode==='real'?'Verified version':'Demo sample'} · v{version?.number}</span></>:<div className="project-cover-fallback"><span className="project-cover-monogram" aria-hidden="true">{project.title.slice(0,2).toUpperCase()}</span><span className="project-cover-note">Project cover · open to review saved work</span></div>}</div>;
}
