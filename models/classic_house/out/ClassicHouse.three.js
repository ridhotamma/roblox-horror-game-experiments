// Classic cottage house - three.js loader (roblox-modeling skill)
// Usage:
//   import { loadClassicHouse } from './ClassicHouse.three.js';
//   const fish = await loadClassicHouse(scene);           // adds it to the scene
//   fish.play('FrontDoorOpen');                         // cross-fades between clips
//   renderer.setAnimationLoop(() => { fish.update(clock.getDelta()); renderer.render(scene, camera); });
// Units are metres, +Y up, the model faces +Z. Needs three r150+ (GLTFLoader from three/addons).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export const CLIPS = [{"name":"FrontDoorOpen","loop":false,"duration":1.6},{"name":"FrontDoorClose","loop":false,"duration":0.65},{"name":"BackDoorOpen","loop":false,"duration":1.6},{"name":"BackDoorClose","loop":false,"duration":0.65},{"name":"RoofLift","loop":false,"duration":1.2},{"name":"RoofLower","loop":false,"duration":1.2}];

export async function loadClassicHouse(parent, url = new URL('./ClassicHouse.glb', import.meta.url).href) {
  const gltf = await new GLTFLoader().loadAsync(url);
  const root = gltf.scene;
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = !o.isSkinnedMesh; } });
  if (parent) parent.add(root);
  const mixer = new THREE.AnimationMixer(root);
  const actions = Object.fromEntries(gltf.animations.map(c => [c.name, mixer.clipAction(c)]));
  for (const c of CLIPS) {
    const a = actions[c.name]; if (!a) continue;
    if (!c.loop) { a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
  }
  let current = null;
  return {
    root, mixer, actions,
    play(name, fade = 0.2) {
      const next = actions[name]; if (!next) throw new Error('no clip ' + name);
      next.reset().play();
      if (current && current !== next) current.crossFadeTo(next, fade, false);
      current = next; return next;
    },
    update(dt) { mixer.update(dt); },
  };
}
