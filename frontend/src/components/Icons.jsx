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
export const IconCrosshair = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="9"/><line x1="12" y1="1" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="1" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="23" y2="12"/></svg>
export const IconSend      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
export const IconSettings  = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-1.4 3.4h-.1a1.7 1.7 0 0 0-1.7 1.1 2 2 0 0 1-3.8 0 1.7 1.7 0 0 0-1.7-1.1H11a2 2 0 0 1-1.4-3.4l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H8.4a2 2 0 0 1-2-1.4 2 2 0 0 1 0-1.2 2 2 0 0 1 2-1.4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 0 1 11 2.6h.1a1.7 1.7 0 0 0 1.7-1.1 2 2 0 0 1 3.8 0 1.7 1.7 0 0 0 1.7 1.1h.1a2 2 0 0 1 1.4 3.4l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1h.1a2 2 0 0 1 0 3.6h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>
export const IconZap       = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polygon points="13 2 3 14 11 14 9 22 19 10 11 10 13 2"/></svg>
export const IconInfo      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
export const IconEye       = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/><circle cx="12" cy="12" r="2.5"/></svg>
export const IconActivity  = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
export const IconMail      = ({size=16,cls='',style={}})=><svg {...S(size,cls,style)}><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></svg>