<script setup lang="ts">
// A link into the live demo (public/demo/: npm run demo), e.g. <Demo at="combat">Try it</Demo>.
import { withBase } from "vitepress";
const props = defineProps<{ page?: "cockpit" | "fleet"; at?: string; query?: string }>();
const href = () => {
  if (props.page === "fleet") return withBase(`/demo/${props.query ? `?${props.query}` : ""}`);
  const q = new URLSearchParams(props.query ?? "");
  if (props.at) q.set("at", props.at);
  const s = q.toString();
  return withBase(`/demo/cockpit.html${s ? `?${s}` : ""}`);
};
</script>

<template>
  <a class="demo-link" :href="href()" target="_self"><span class="tag">Live demo</span><slot /></a>
</template>
