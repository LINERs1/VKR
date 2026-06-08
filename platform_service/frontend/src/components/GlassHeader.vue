<script setup>
</script>

<template>
  <div class="topbar-wrapper">
    <div class="ambient-orb orb-1"></div>
    <div class="ambient-orb orb-2"></div>
    <header class="topbar">
      <div class="topbar-inner">
        <slot></slot>
      </div>
    </header>
  </div>
</template>

<style scoped>
/* ─── Topbar Wrapper & Ambient Orbs ──────────────────────── */
.topbar-wrapper {
  position: sticky;
  top: 0;
  width: 100%;
  display: flex;
  justify-content: center;
  padding-top: 24px;
  margin-bottom: 32px;
  z-index: 100;
}
.ambient-orb {
  position: absolute;
  top: 0px;
  width: 400px;
  height: 200px;
  border-radius: 50%;
  filter: blur(80px);
  z-index: 0;
  opacity: 0.25;
  pointer-events: none;
}
.orb-1 { left: 10%; background: #00ffc8; }
.orb-2 { right: 10%; background: #9d4edd; }

/* ─── Topbar ─────────────────────────────────────────────── */
.topbar {
  position: relative;
  max-width: 1100px;
  width: calc(100% - 48px);
  border-radius: 100px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(32px) saturate(150%);
  -webkit-backdrop-filter: blur(32px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4),
              0 10px 20px rgba(0, 255, 200, 0.1),
              0 10px 40px rgba(157, 78, 221, 0.1),
              inset 0 1px 0 rgba(255,255,255,0.05);
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.topbar:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5),
              0 15px 30px rgba(0, 255, 200, 0.2),
              0 15px 60px rgba(157, 78, 221, 0.2),
              inset 0 1px 0 rgba(255,255,255,0.1);
  transform: translateY(-2px);
}

.topbar-inner {
  max-width: none;
  width: 100%;
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
</style>
