/* WeaponShield AI – Inline SVG Icons (Lucide-style) */
const B = { fill:'none', stroke:'currentColor', strokeWidth:2, strokeLinecap:'round', strokeLinejoin:'round' }
const S = (size, cls, style) => ({ ...B, width:size, height:size, viewBox:'0 0 24 24', className:cls, style })

export const IconShield    = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
export const IconVideo     = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
export const IconImage     = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
export const IconCamera    = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
export const IconPlay      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polygon points="5 3 19 12 5 21 5 3"/></svg>
export const IconStop      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
export const IconUpload    = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>
export const IconDownload  = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/></svg>
export const IconAlert     = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
export const IconCheck     = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
export const IconX         = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
export const IconActivity  = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
export const IconEye       = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
export const IconInfo      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
export const IconSend      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
export const IconZap       = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
export const IconSettings  = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
export const IconCrosshair = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>
