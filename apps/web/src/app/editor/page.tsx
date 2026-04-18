import dynamic from "next/dynamic";

const EditorApp = dynamic(() => import("./EditorApp"), { ssr: false });

export default function EditorPage() {
  return <EditorApp />;
}
