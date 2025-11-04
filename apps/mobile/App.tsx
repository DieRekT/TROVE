import React, { useState } from "react";
import SearchScreen from "./src/screens/SearchScreen";
import ArticleScreen from "./src/screens/ArticleScreen";
export default function App(){
  const [open, setOpen] = useState<string|undefined>(undefined);
  if (open) return <ArticleScreen idOrUrl={open} onBack={()=>setOpen(undefined)} />
  return <SearchScreen onOpen={(id)=>setOpen(id)} />
}

