import {createContext, useContext} from 'react';

// Templates read this to switch between the 16:9 episode layout and the 9:16 Short layout.
// In the Short, a template fills a stage of w x h (not the whole frame).
// `bare` hides a template's own kicker/title when the panel's left column already shows the headline.
export const LayoutCtx = createContext({v: false, w: 1920, h: 1080, bare: false});
export const useLayout = () => useContext(LayoutCtx);
