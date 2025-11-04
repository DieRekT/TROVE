import React from "react";
import { View, Text } from "react-native";


export default function TermModeBanner() {
  return (
    <View style={{ backgroundColor:"#222", padding:10, borderRadius:8, marginBottom:8 }}>
      <Text style={{ color:"#fff", fontWeight:"600" }}>
        Sensitive Research Mode
      </Text>
      <Text style={{ color:"#ddd", marginTop:4, fontSize:12 }}>
        Includes historically offensive terms to improve archival recall. You may encounter harmful language. This is optional and can be turned off anytime.
      </Text>
    </View>
  );
}

