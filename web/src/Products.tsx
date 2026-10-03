import {useEffect,useState} from 'react';
import {ArrowUpRight,Building2,ChevronLeft,ChevronRight,CircleHelp,ExternalLink,FileSearch,Gauge,LoaderCircle,Package,Search,Sparkles,TriangleAlert} from 'lucide-react';
import './products.css';

type Row=Record<string,any>;
type Props={qs:string;version:number;onCompany:(ruc:string)=>void};
const n=(v:any,d=0)=>v==null?'—':new Intl.NumberFormat('es-PE',{maximumFractionDigits:d,minimumFractionDigits:d}).format(Number(v));
const usd=(v:any)=>v==null?'—':new Intl.NumberFormat('es-PE',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(Number(v));
const d=(v:any)=>v?new Date(String(v).slice(0,10)+'T12:00:00').toLocaleDateString('es-PE',{day:'2-digit',month:'short',year:'numeric'}):'—';
const mi=(v:any)=>v==null?null:String(Number(v));
const sourceLabel:Row={'ficha técnica':'según ficha técnica','declaración':'declarado en la DUA','correlación':'inferido de otras DUA del mismo grado'};
const examples=['HDPE inyección','HDPE soplado MI 0.35','PP rafia','LLDPE film MI 1','PET botellas','Certene'];
const PAGE=12;

function useProducts(path:string,version:number){
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 useEffect(()=>{let live=true;setLoading(true);setError('');
  fetch('/api'+path,{headers:{'X-Radar-Token':localStorage.getItem('radar-token')||''}})
   .then(async r=>{if(!r.ok){let e:any;try{e=await r.json()}catch{e={}};throw new Error(e.detail||r.statusText)}return r.json()})
   .then(j=>{if(live)setData(j)}).catch(e=>{if(live)setError(e.message)}).finally(()=>{if(live)setLoading(false)});
  return()=>{live=false}},[path,version]);
 return {data,error,loading};
}

function Interpretation({p}:{p:Row}){
 const chips:[string,string][]=[];
 if(p.family)chips.push(['Polímero',p.family]);
 if(p.application)chips.push(['Proceso',p.application]);
 if(p.mi_min!=null||p.mi_max!=null)chips.push(['Melt index',p.mi_min!=null&&p.mi_max!=null?mi(p.mi_min)+' – '+mi(p.mi_max)+' g/10 min':p.mi_min!=null?'≥ '+mi(p.mi_min):'≤ '+mi(p.mi_max)]);
 (p.terms||[]).forEach((t:string)=>chips.push(['Marca / grado',t]));
 if(!chips.length)return null;
 return <div className="pr-interp"><Sparkles size={14}/><span>Interpretado como</span>{chips.map(([k,v],i)=><span className="pr-chip" key={i}><small>{k}</small>{v}</span>)}</div>;
}

function MiBox({g}:{g:Row}){
 if(g.melt_index==null)return <div className="pr-mi empty"><Gauge size={15}/><div><b>MI no informado</b><small>{g.family==='PET'&&g.iv?'IV '+g.iv+' dL/g':'Ni la DUA ni la ficha lo indican'}</small></div></div>;
 const range=g.mi_min!=null&&g.mi_max!=null&&Number(g.mi_min)!==Number(g.mi_max);
 return <div className="pr-mi"><Gauge size={15}/><div><b>MI {mi(g.melt_index)} <span>g/10 min</span></b><small>{g.mi_condition||''}{range?' · declarado '+mi(g.mi_min)+'–'+mi(g.mi_max):''}</small><small className="pr-src">{sourceLabel[g.mi_source]||''}</small></div></div>;
}

function GradeCard({g,want,onCompany}:{g:Row;want?:string;onCompany:(ruc:string)=>void}){
 const [open,setOpen]=useState(false);
 const buyers:Row[]=g.buyers||[];const shown=open?buyers:buyers.slice(0,4);
 const secondary=want&&g.application&&g.application!==want;
 return <article className="pr-card">
  <header><div><h3>{g.product_name||g.grade}</h3><p>{[g.brand,g.grade,g.polymer||g.family].filter(Boolean).join(' · ')}</p></div><MiBox g={g}/></header>
  <div className="pr-tags">{g.applications?.map((a:string)=><span key={a} className={'badge '+(a===g.application?'green':'')}>{a}</span>)}
   {secondary&&<span className="badge amber">Uso secundario: su ficha prioriza {g.application}</span>}
   {g.application_source&&<span className="pr-meta">Proceso {sourceLabel[g.application_source]||g.application_source}</span>}
   {g.catalog?<span className="pr-meta">Ficha verificada · confianza {g.confidence}</span>:<span className="pr-meta">Sin ficha técnica verificada</span>}</div>
  {g.summary&&<p className="pr-summary">{g.summary}</p>}
  {g.mi_hint&&g.summary&&!g.summary.includes(g.mi_hint)&&<p className="pr-hint">Lectura del MI: {g.mi_hint}.</p>}
  {g.application_mismatch&&<p className="pr-warn"><TriangleAlert size={13}/>Alguna DUA declara un uso distinto al de la ficha técnica; prevalece la ficha.</p>}
  <div className="pr-stats"><span><b>{n(g.tonnes,1)} t</b>volumen</span><span><b>{n(g.importers)}</b>empresas</span><span><b>{n(g.operations)}</b>operaciones</span><span><b>{n(g.cif_kg,3)}</b>CIF USD/kg</span><span><b>{d(g.last)}</b>última</span>{g.source_url&&<a href={g.source_url} target="_blank" rel="noreferrer"><ExternalLink size={13}/> Ficha técnica</a>}</div>
  <table className="pr-buyers"><thead><tr><th>Empresa importadora</th><th className="numeric">t</th><th className="numeric">CIF USD/kg</th><th>Origen</th><th>Última</th></tr></thead>
   <tbody>{shown.map(b=><tr key={b.importer_ruc||b.importer}><td><button onClick={()=>b.importer_ruc&&onCompany(b.importer_ruc)}>{b.importer||'RUC '+(b.importer_ruc||'no informado')}</button><small>{b.importer_ruc}</small></td><td className="numeric">{n(b.tonnes,1)}</td><td className="numeric">{n(b.cif_kg,3)}</td><td>{b.origins||'—'}</td><td>{d(b.last)}</td></tr>)}</tbody></table>
  {buyers.length>4&&<button className="text-btn pr-more" onClick={()=>setOpen(!open)}>{open?'Ver menos':'Ver las '+buyers.length+' empresas'}</button>}
 </article>;
}

export default function Products({qs,version,onCompany}:Props){
 const [draft,setDraft]=useState(''),[query,setQuery]=useState(''),[page,setPage]=useState(1),[sort,setSort]=useState('tonnes');
 useEffect(()=>setPage(1),[query,qs,sort]);
 const params=new URLSearchParams(qs);params.delete('q');params.set('p',query);params.set('sort',sort);params.set('page',String(page));params.set('page_size',String(PAGE));
 const {data,error,loading}=useProducts('/products?'+params.toString(),version);
 const run=(t:string)=>{setDraft(t);setQuery(t)};
 const s=data?.summary;const grades=data?.grades;
 return <>
  <form className="search-panel" onSubmit={e=>{e.preventDefault();setQuery(draft)}}><div className="search-box"><Search size={20}/><input aria-label="Buscar producto" placeholder="Describe el producto: HDPE inyección, PP rafia MI 3, Certene HI-864U…" value={draft} onChange={e=>setDraft(e.target.value)}/><kbd>↵</kbd></div><button type="submit" className="btn search-btn">Buscar producto</button></form>
  <div className="search-suggestions"><span>Prueba con</span>{examples.map(t=><button key={t} onClick={()=>run(t)}>{t}<ArrowUpRight size={11}/></button>)}<span className="search-caution">Polímero, proceso y MI se detectan en la búsqueda; marca y código se buscan literal.</span></div>
  {data&&<Interpretation p={data.interpretation}/>}
  {error?<div className="error">{error}</div>:loading&&!data?<div className="loading"><LoaderCircle className="spin" size={22}/> Analizando productos…</div>:data&&<>
   <div className="metrics pr-metrics">{[['Empresas importadoras',n(s.importers),'RUC únicos que lo importaron',Building2],['Grados identificados',n(s.grades),n(s.ungraded_series)+' series sin código detectable',Package],['Volumen',n(s.tonnes,1)+' t','Peso neto declarado',Package],['CIF ponderado',n(s.cif_kg,3),'USD/kg · misma serie',Gauge],['Operaciones',n(s.operations),n(s.series)+' series · '+d(s.start)+' – '+d(s.end),FileSearch]].map(([label,value,hint,Icon]:any)=><article className="metric" key={label}><div className="metric-label">{label}<Icon size={16}/></div><strong>{value}</strong><small>{hint}</small></article>)}</div>
   {!s.series?<div className="empty"><FileSearch size={32}/><h3>Sin importaciones para este producto</h3><p>Prueba con menos términos o amplía el rango de fechas.</p></div>:<>
   <div className="pr-layout">
    <section className="panel"><div className="panel-heading"><div><h2>Empresas que importaron este producto <span className="count">{n(data.importers.length)}</span></h2><p>Incluye series sin código de grado detectable. El proveedor extranjero no es público en SUNAT; se muestra el productor o marca declarada.</p></div></div>
     <div className="table-scroll pr-importers"><table><thead><tr><th>Empresa / RUC</th><th className="numeric">Toneladas</th><th className="numeric">CIF USD/kg</th><th>Grados · marcas</th><th>Última</th></tr></thead><tbody>{data.importers.map((r:Row)=><tr key={r.ruc||r.name} onClick={()=>r.ruc&&onCompany(r.ruc)}><td className="company-cell"><b>{r.name||'RUC '+(r.ruc||'no informado')}</b><small>{r.ruc} · {n(r.operations)} operaciones</small></td><td className="numeric">{n(r.tonnes,1)}</td><td className="numeric price">{n(r.cif_kg,3)}</td><td className="pr-list"><span title={r.grades}>{r.grades||'Sin código'}</span><small title={r.brands}>{r.brands||'Marca no informada'}</small></td><td>{d(r.last)}</td></tr>)}</tbody></table></div></section>
    <section className="panel"><div className="panel-heading"><div><h2>Productores / marcas</h2><p>Detectados en la descripción comercial</p></div></div>
     <ul className="pr-brands">{data.brands.map((b:Row)=><li key={b.name}><b>{b.name}</b><span>{n(b.tonnes,1)} t · {n(b.grades)} grados</span></li>)}{!data.brands.length&&<li className="muted">Sin marca declarada</li>}</ul></section>
   </div>
   <div className="pr-grades-head"><h2>Grados encontrados <span className="count">{n(grades.total)}</span></h2><label>Ordenar por <select value={sort} onChange={e=>setSort(e.target.value)}><option value="tonnes">Volumen</option><option value="importers">N.º de empresas</option><option value="cif_usd">Valor CIF</option><option value="cif_kg">CIF USD/kg</option><option value="melt_index">Melt index</option><option value="last">Más reciente</option></select></label></div>
   <div className="pr-grades">{grades.items.map((g:Row)=><GradeCard key={g.grade_key} g={g} want={data.interpretation.application} onCompany={onCompany}/>)}</div>
   {grades.total>PAGE&&<div className="pagination"><span>{(page-1)*PAGE+1}–{Math.min(page*PAGE,grades.total)} de {n(grades.total)} grados</span><div><button className="icon-btn" disabled={page===1} onClick={()=>setPage(p=>p-1)} aria-label="Página anterior"><ChevronLeft size={18}/></button><span>Página {page} de {Math.ceil(grades.total/PAGE)}</span><button className="icon-btn" disabled={page*PAGE>=grades.total} onClick={()=>setPage(p=>p+1)} aria-label="Página siguiente"><ChevronRight size={18}/></button></div></div>}
   <div className="notice"><CircleHelp size={15}/><span>Nombre, proceso y MI provienen de la ficha técnica del grado cuando está verificada; si no, de lo declarado en la DUA o de otras DUA del mismo código. El MI de PE se mide a 190 °C/2.16 kg y el de PP a 230 °C/2.16 kg: no son comparables entre sí.</span></div>
   </>}
  </>}
 </>;
}
