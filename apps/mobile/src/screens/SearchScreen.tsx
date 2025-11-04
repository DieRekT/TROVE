import React, { useState } from "react";
import { View, TextInput, Switch, Text, FlatList, SafeAreaView, ActivityIndicator, Button, Pressable, TouchableOpacity } from "react-native";
import { searchTrove } from "../api";
import ResultItem from "../components/ResultItem";
import TermModeBanner from "../components/TermModeBanner";
import TunnelQRModal from "../components/TunnelQRModal";


export default function SearchScreen({ onOpen }: { onOpen:(idOrUrl:string)=>void }) {
  const [q, setQ] = useState("");
  const [sens, setSens] = useState(false);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<any[]>([]);
  const [queryUsed, setQueryUsed] = useState("");
  const [showQR, setShowQR] = useState(false);


  async function run() {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await searchTrove(q, sens);
      setItems(res.items || []);
      setQueryUsed(res.query_used || q);
    } catch (e: any) {
      console.error("Search error:", e);
      setItems([]);
      setQueryUsed("");
      // Show error - in production you'd use Alert.alert
    } finally { setLoading(false); }
  }


  return (
    <SafeAreaView style={{ flex:1, padding:12 }}>
      <View style={{ flexDirection:"row", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
        <Text style={{ fontSize:20, fontWeight:"700" }}>Archive Detective</Text>
        <TouchableOpacity 
          onPress={()=>setShowQR(true)}
          style={{ backgroundColor:"#0066cc", paddingHorizontal:12, paddingVertical:6, borderRadius:6 }}
        >
          <Text style={{ color:"white", fontWeight:"600" }}>🔗 QR</Text>
        </TouchableOpacity>
      </View>
      
      <TunnelQRModal visible={showQR} onClose={()=>setShowQR(false)} />

      <View style={{ flexDirection:"row", gap:8, alignItems:"center" }}>
        <TextInput
          placeholder="Search Trove…"
          value={q}
          onChangeText={setQ}
          style={{ flex:1, borderWidth:1, borderColor:"#ddd", padding:10, borderRadius:8 }}
          onSubmitEditing={run}
        />
        <TouchableOpacity 
          onPress={run}
          disabled={loading || !q.trim()}
          style={{ 
            backgroundColor: loading || !q.trim() ? "#ccc" : "#0066cc", 
            paddingHorizontal:16, 
            paddingVertical:10, 
            borderRadius:8 
          }}
        >
          <Text style={{ color:"white", fontWeight:"600" }}>Search</Text>
        </TouchableOpacity>
      </View>

      <View style={{ marginTop:8, flexDirection:"row", alignItems:"center", gap:10 }}>
        <Switch value={sens} onValueChange={setSens} />
        <Text>Sensitive Research Mode</Text>
      </View>
      {sens && <TermModeBanner />}

      {loading ? <ActivityIndicator style={{ marginTop:12 }} /> : null}

      {queryUsed ? <Text style={{ fontSize:12, color:"#666", marginVertical:6 }}>Query used: {queryUsed}</Text> : null}

      <FlatList
        data={items}
        keyExtractor={(it)=>String(it.id)}
        renderItem={({item}) => (
          <ResultItem item={item} onPress={()=>onOpen(item.troveUrl || `https://trove.nla.gov.au/newspaper/article/${item.id}`)} />
        )}
      />
    </SafeAreaView>
  );
}

