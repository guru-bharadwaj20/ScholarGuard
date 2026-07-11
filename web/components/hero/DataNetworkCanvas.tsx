"use client";

import * as React from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * A slowly rotating network of glowing nodes joined by thin lines —
 * figures and their similarity relationships, the thing the pipeline
 * actually computes (Stage 3 builds exactly this graph). Instanced
 * spheres + one LineSegments geometry keep it cheap on any GPU.
 *
 * This file is only ever loaded via dynamic import (ssr: false) and only
 * when prefers-reduced-motion is NOT set — the static poster fallback
 * lives in HeroSection.
 */

const NODE_COUNT = 56;
const LINK_DISTANCE = 1.35;
const ACCENT = new THREE.Color("#8b93f8");

function buildGraph(seedRandom: () => number) {
  const positions: THREE.Vector3[] = [];
  for (let i = 0; i < NODE_COUNT; i++) {
    // Nodes on a fuzzy sphere shell so the silhouette reads as one object.
    const r = 1.7 + seedRandom() * 0.9;
    const theta = seedRandom() * Math.PI * 2;
    const phi = Math.acos(2 * seedRandom() - 1);
    positions.push(
      new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta) * 0.72, // slightly squashed
        r * Math.cos(phi),
      ),
    );
  }
  const linkPairs: [number, number][] = [];
  for (let i = 0; i < NODE_COUNT; i++) {
    for (let j = i + 1; j < NODE_COUNT; j++) {
      if (positions[i].distanceTo(positions[j]) < LINK_DISTANCE) {
        linkPairs.push([i, j]);
      }
    }
  }
  return { positions, linkPairs };
}

// Deterministic PRNG so the scene is identical every load (no hydration
// flicker, stable screenshots).
function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function Network() {
  const group = React.useRef<THREE.Group>(null);
  const { positions, linkPairs } = React.useMemo(
    () => buildGraph(mulberry32(2026)),
    [],
  );

  const lineGeometry = React.useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const verts = new Float32Array(linkPairs.length * 6);
    linkPairs.forEach(([a, b], i) => {
      verts.set([...positions[a].toArray(), ...positions[b].toArray()], i * 6);
    });
    geo.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    return geo;
  }, [positions, linkPairs]);

  const instanced = React.useRef<THREE.InstancedMesh>(null);
  React.useEffect(() => {
    if (!instanced.current) return;
    const m = new THREE.Matrix4();
    positions.forEach((p, i) => {
      m.makeTranslation(p.x, p.y, p.z);
      instanced.current!.setMatrixAt(i, m);
    });
    instanced.current.instanceMatrix.needsUpdate = true;
  }, [positions]);

  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = clock.elapsedTime;
    group.current.rotation.y = t * 0.06;
    group.current.rotation.x = Math.sin(t * 0.05) * 0.12;
  });

  return (
    <group ref={group}>
      <instancedMesh ref={instanced} args={[undefined, undefined, NODE_COUNT]}>
        <sphereGeometry args={[0.035, 12, 12]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.9} />
      </instancedMesh>
      <lineSegments geometry={lineGeometry}>
        <lineBasicMaterial color={ACCENT} transparent opacity={0.16} />
      </lineSegments>
    </group>
  );
}

export default function DataNetworkCanvas() {
  return (
    <Canvas
      camera={{ position: [0, 0, 5.4], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      dpr={[1, 1.75]}
      style={{ background: "transparent" }}
    >
      <Network />
    </Canvas>
  );
}
