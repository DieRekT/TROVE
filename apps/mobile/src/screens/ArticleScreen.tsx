import React, { useEffect, useState } from "react";
import { SafeAreaView, View, Text, ScrollView, Button, Alert } from "react-native";
import { fetchArticle, summarize } from "../api";
import * as Print from "expo-print";
import * as Speech from "expo-speech";
import * as Sharing from "expo-sharing";


export default function ArticleScreen({ idOrUrl, onBack }:{ idOrUrl:string, onBack:()=>void }) {
  const [art, setArt] = useState<any>(null);
  const [sum, setSum] = useState<string>("");


  useEffect(()=>{
    fetchArticle(idOrUrl).then(setArt).catch(e=>Alert.alert("Error", String(e)));
  }, [idOrUrl]);


  async function doSummarize() {
    if (!art) return;
    const res = await summarize(art.text);
    setSum(res.summary);
  }


  async function doPrint() {
    if (!art) return;
    const html = `
      <html><body>
        <h2>${art.heading || art.title || "Trove article"}</h2>
        <div style="color:#666;font-size:12px">${art.date} · Page ${art.page || "?"} · <a href="${art.troveUrl}">${art.troveUrl}</a></div>
        <pre style="white-space:pre-wrap;font-family:serif">${art.text}</pre>
      </body></html>`;
    const { uri } = await Print.printToFileAsync({ html });
    await Sharing.shareAsync(uri);
  }


  function speak() {
    if (art?.text) Speech.speak(art.text, { language: "en-AU", rate: 0.9 });
  }


  return (
    <SafeAreaView style={{ flex:1, padding:12 }}>
      <Button title="← Back" onPress={onBack} />
      {!art ? <Text>Loading…</Text> :
       <ScrollView>
         <Text style={{ fontSize:20, fontWeight:"700", marginTop:8 }}>{art.heading || art.title}</Text>
         <Text style={{ color:"#666" }}>{art.date} · Page {art.page || "?"}</Text>
         <View style={{ flexDirection:"row", gap:8, marginVertical:8 }}>
           <Button title="Summarize" onPress={doSummarize} />
           <Button title="Read Aloud" onPress={speak} />
           <Button title="Print/Export" onPress={doPrint} />
         </View>
         {sum ? <View style={{ backgroundColor:"#f8f8f8", padding:8, borderRadius:8, marginBottom:8 }}>
           <Text style={{ fontWeight:"600" }}>Summary</Text>
           <Text>{sum}</Text>
         </View> : null}
         <Text style={{ fontSize:16, lineHeight:22 }}>{art.text}</Text>
       </ScrollView>
      }
    </SafeAreaView>
  );
}

