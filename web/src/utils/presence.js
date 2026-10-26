let fallback
export function presenceDeviceId(){
 try{let id=sessionStorage.getItem('yanshi:device');if(!id){id=crypto.randomUUID();sessionStorage.setItem('yanshi:device',id)}return id}
 catch{return fallback ||= `device-${Math.random().toString(36).slice(2)}`}
}
