import { redirect } from "next/navigation";

// There is one job on opening this app: decide on what came in.
export default function Home() {
  redirect("/triage");
}
