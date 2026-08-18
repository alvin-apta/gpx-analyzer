import type {Trip} from './types';
export async function listTrips():Promise<Trip[]>{return fetch('/api/trips').then(r=>r.json())}
export async function getTrip(id:string):Promise<Trip>{return fetch(`/api/trips/${id}`).then(r=>{if(!r.ok)throw Error('Trip unavailable');return r.json()})}
export async function upload(file:File,mode:string){const d=new FormData();d.append('file',file);d.append('mode',mode);const r=await fetch('/api/trips',{method:'POST',body:d});if(!r.ok)throw Error((await r.json()).detail);return r.json()}
export async function explain(id:string){const r=await fetch(`/api/trips/${id}/explanation`,{method:'POST'});if(!r.ok)throw Error((await r.json()).detail);return r.json()}
export async function deleteTrip(id:string){const r=await fetch(`/api/trips/${id}`,{method:'DELETE'});if(!r.ok)throw Error((await r.json()).detail||'Delete failed')}
