<script setup lang="ts">
// A short silent clip from public/shots/ (npm run shots records them), looping like a GIF.
import { withBase } from "vitepress";
const props = defineProps<{ name: string; caption?: string }>();
</script>

<template>
  <figure class="clip">
    <video :src="withBase(`/shots/${props.name}.webm`)" :poster="withBase(`/shots/${props.name}.jpg`)" autoplay muted loop playsinline preload="metadata"></video>
    <figcaption v-if="caption">{{ caption }}</figcaption>
  </figure>
</template>
