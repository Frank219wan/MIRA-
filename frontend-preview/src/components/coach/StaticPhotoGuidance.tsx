import { useEffect, useState } from 'react';
import { getCuratedReference, getStaticGuidance } from '../../services/staticGuidance';
import { Button } from '../ui/button';
import { getStaticFace } from '../../services/staticFace';
export function StaticPhotoGuidance() {
  const [reference, setReference] = useState<Awaited<ReturnType<typeof getCuratedReference>>>();
  const [result,setResult] = useState<Awaited<ReturnType<typeof getStaticGuidance>>>();
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [selected,setSelected] = useState('');
  useEffect(() => {
    let active = true;
    getCuratedReference().then(value => { if (active) setReference(value); }).catch(e => {
      if (active) setError(e instanceof Error ? e.message : '暂时无法读取教程。');
    });
    return () => { active = false; };
  }, []);
  async function load(action: 'A02'|'A04') {
    setBusy(true); setError(''); setResult(undefined);
    try {
      setSelected(action); setResult(await getStaticGuidance(action));
    } catch(e) {setError(e instanceof Error ? e.message : '暂时无法读取指导。');}
    finally {setBusy(false);}
  }
  return <section className="static-photo-guidance">
    {reference && <>
      <h3>{reference.title}</h3>
      <ol>{reference.steps.map(step => <li key={step.action_id}>{step.instruction}</li>)}</ol>
      {getStaticFace() && <div className="action-row">{reference.steps.map(step=><Button key={step.action_id} variant="outline" disabled={busy || !getStaticFace()} onClick={()=>load(step.action_id)} aria-pressed={selected===step.action_id}>{step.title}</Button>)}</div>}
      {result && <><div className="static-photo-canvas"><img src={result.image} alt="本次本人照片上的参考指导"/><svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="静态照片定位指导">{result.shapes.map(s=>s.guidance_type==='direction_line' && s.anchor && s.endpoint ? <line key={s.side} x1={s.anchor.x_norm} y1={s.anchor.y_norm} x2={s.endpoint.x_norm} y2={s.endpoint.y_norm} stroke="white" strokeWidth=".003"/> : <polygon key={s.side} points={s.polygon?.map(p=>`${p.x_norm},${p.y_norm}`).join(' ')} fill="#ffffff40" stroke="white" strokeWidth=".002"/>)}</svg></div><p>{reference.steps.find(s=>s.action_id===selected)?.instruction}</p><small>静态辅助线，请对照镜中妆效操作。</small></>}
    </>}
    {busy && <p role="status">正在生成照片指导…</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
