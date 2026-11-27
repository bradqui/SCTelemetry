<script lang="ts">
  // The Starglance wings, in the theme's colours: wings and diamond in the accent, the star
  // in the second accent. The same drawing as site/public/logo.svg.
</script>

<svg class="logo" viewBox="1 13 62 38" aria-hidden="true">
  <g class="w">
    <polygon points="21,26.5 3,20.5 6.5,25.5 21,30.5" /><polygon points="43,26.5 61,20.5 57.5,25.5 43,30.5" />
    <g fill-opacity=".72">
      <polygon points="21,33 7.5,28.5 10.5,33 21.5,37" /><polygon points="43,33 56.5,28.5 53.5,33 42.5,37" />
    </g>
    <g fill-opacity=".45">
      <polygon points="22.5,39.5 12.5,36.5 15.5,40.5 24,43" /><polygon points="41.5,39.5 51.5,36.5 48.5,40.5 40,43" />
    </g>
  </g>
  <path class="d" d="M32 15 44.5 32 32 49 19.5 32Z" />
  <path class="s" d="M32 25.3L33.7 30.15L38.85 30.28L34.76 33.4L36.23 38.32L32 35.4L27.77 38.32L29.24 33.4L25.15 30.28L30.3 30.15Z" />
</svg>

<style>
  .logo {
    display: block;
    flex: none;
    height: 22px;
    width: auto;
    aspect-ratio: 62 / 38;
  }
  .w {
    fill: var(--accent);
  }
  .d {
    fill: color-mix(in srgb, var(--accent) 14%, transparent);
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linejoin: round;
  }
  .s {
    fill: var(--accent-2);
  }
</style>
