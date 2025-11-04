import React from "react";
import { Pressable, View, Text } from "react-native";


export default function ResultItem({ item, onPress }: { item: any, onPress: ()=>void }) {
  return (
    <Pressable onPress={onPress} style={{ paddingVertical:10, borderBottomWidth:1, borderColor:"#eee" }}>
      <Text style={{ fontWeight:"600" }}>{item.title || "(untitled)"}</Text>
      <Text style={{ color:"#666" }}>{item.date} · Page {item.page || "?"}</Text>
      {item.snippet ? <Text style={{ color:"#333", marginTop:4 }}>{item.snippet}</Text> : null}
    </Pressable>
  );
}

