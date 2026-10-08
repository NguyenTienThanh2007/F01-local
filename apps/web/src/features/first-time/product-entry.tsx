'use client';
import Link from 'next/link';
import {useState} from 'react';
import {ProjectPlanningForm} from '@/features/project-planning/project-planning-form';
import {projectStarters,type StarterId} from '@/features/project-planning/project-starters';
import {SampleInterface} from './sample-interface';
import {LifecycleDemo} from './lifecycle-demo';
import {EntryNavigation} from './entry-navigation';
import {PlatformIndex} from './platform-index';

export function ProductEntry(){
 const [starter,setStarter]=useState<StarterId>('crm');
 const example=projectStarters.find(item=>item.id===starter)!;
 return <div className="entry-page os-entry welcome-page">
  <a href="#main-content" className="skip-link">Skip to content</a><EntryNavigation/>
  <main id="main-content" tabIndex={-1}>
   <section className="welcome-hero" aria-labelledby="welcome-title">
    <div className="welcome-promise"><span className="meta">F01 / YOUR SOFTWARE FACTORY</span><h1 id="welcome-title">Your idea.<br/>Working <em>software.</em></h1><p>Describe the browser app you need. F01 turns your brief into a plan, builds it and checks it. You preview the result before you publish.</p><Link className="button button-primary" href="/projects/new">Create a project <span aria-hidden="true">↗</span></Link><span className="welcome-assurance">You approve the plan. You decide when it goes live.</span></div>
    <div className="welcome-example"><div className="example-caption"><span>WHAT YOU COULD MAKE</span><span>Illustration</span></div><div className="example-switch" role="group" aria-label="Example applications">{projectStarters.map(item=><button key={item.id} aria-pressed={item.id===starter} onClick={()=>setStarter(item.id)}>{item.short}</button>)}</div><div className="example-window"><SampleInterface starter={starter}/></div><Link className="example-use" href={`/projects/new?starter=${example.id}`}>Start with {example.title.toLowerCase()} <span aria-hidden="true">↗</span></Link></div>
   </section>
   <section id="platform" className="welcome-process" aria-labelledby="process-title"><div><span className="meta">FROM FIRST BRIEF TO NEXT VERSION</span><h2 id="process-title">A clear path.<br/>Your decisions.</h2></div><ol>{[['Plan & approve','Tell F01 what should exist. Review the proposed work before a build starts.'],['Build & preview','Follow saved progress. Try the verified application and decide what needs changing.'],['Publish & evolve','Publish the version you reviewed. Make changes while your live release stays in place.']].map(([title,copy],index)=><li key={title}><span className="process-number">{String(index+1).padStart(2,'0')}</span><h3>{title}</h3><p>{copy}</p></li>)}</ol></section>
   <section id="templates" className="welcome-starters" aria-labelledby="welcome-starters-title"><div className="section-heading"><h2 id="welcome-starters-title">Start with something useful.</h2><p>Choose a brief, then make it your own.</p></div><div className="welcome-starter-list">{projectStarters.map(item=><Link href={`/projects/new?starter=${item.id}`} key={item.id}><span className="meta">{item.number}</span><div><h3>{item.title}</h3><p>{item.category}</p></div><span aria-hidden="true">↗</span></Link>)}</div></section>
   <details className="welcome-draft"><summary>Want to explore a draft before saving a project?</summary><p>A draft plan stays on this page. Create a project when you want to build and keep its history.</p><ProjectPlanningForm presentation="home" onStarterChange={setStarter} companion={<LifecycleDemo starter={starter}/>}/></details>
   <section id="docs" className="welcome-faq" aria-labelledby="welcome-faq-title"><h2 id="welcome-faq-title">Before you begin.</h2><div><details><summary>What happens after I create a project?</summary><p>Your original brief is saved. Make a plan, approve it, then start a build. F01 verifies the application before offering a preview. Publishing is a separate decision.</p></details><details><summary>What can I build today?</summary><p>Browser applications with browser state: dashboards, schedules, small tools and games. Applications that need a server, shared database or app secrets are outside the current publishing profile.</p></details><details><summary>Can I change an app that is already live?</summary><p>Yes. Describe the change, approve its plan and rebuild. Preview the new version before publishing. Your previous live release stays in place until a new release passes its checks.</p></details></div></section>
   <details id="connections" className="welcome-advanced"><summary>Project Brain, Build Trace & workspace details</summary><PlatformIndex/></details>
  </main><footer className="entry-footer"><span>F01 / CREATE · RUN · MANAGE · EVOLVE</span><Link href="/projects">Return to your projects ↗</Link></footer>
 </div>;
}
