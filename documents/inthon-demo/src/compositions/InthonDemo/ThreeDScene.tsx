import React, { useMemo } from "react";
import { useCurrentFrame, interpolate, random } from "remotion";
import { ThreeCanvas } from "@remotion/three";

interface ThreeDSceneProps {
  slideIndex: number;
  durationInFrames: number;
}

// -------------------------------------------------------------
// Slide 1: Terminal Shell (pip install inthon)
// -------------------------------------------------------------
const TerminalShell: React.FC = () => {
  const frame = useCurrentFrame();

  // Floating rotation
  const rotX = Math.sin(frame * 0.02) * 0.15;
  const rotY = frame * 0.006;
  const rotZ = Math.cos(frame * 0.02) * 0.08;

  return (
    <group rotation={[rotX, rotY, rotZ]}>
      {/* Main Board representing terminal window */}
      <mesh>
        <boxGeometry args={[4.4, 2.8, 0.1]} />
        <meshStandardMaterial
          color="#121214"
          roughness={0.4}
          metalness={0.8}
          emissive="#08080a"
        />
      </mesh>

      {/* Red, Yellow, Green window buttons */}
      <mesh position={[-1.8, 1.1, 0.08]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color="#ff5f56" roughness={0.1} metalness={0.9} />
      </mesh>
      <mesh position={[-1.5, 1.1, 0.08]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color="#ffbd2e" roughness={0.1} metalness={0.9} />
      </mesh>
      <mesh position={[-1.2, 1.1, 0.08]}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial color="#27c93f" roughness={0.1} metalness={0.9} />
      </mesh>

      {/* Command prompt symbol shape inside the window */}
      <group position={[-1.7, 0.5, 0.06]}>
        {/* Terminal '>' prompt */}
        <mesh position={[0, 0, 0]} rotation={[0, 0, -Math.PI / 4]}>
          <boxGeometry args={[0.2, 0.04, 0.02]} />
          <meshStandardMaterial color="#00f2fe" emissive="#00f2fe" emissiveIntensity={0.6} />
        </mesh>
        <mesh position={[0, -0.12, 0]} rotation={[0, 0, Math.PI / 4]}>
          <boxGeometry args={[0.2, 0.04, 0.02]} />
          <meshStandardMaterial color="#00f2fe" emissive="#00f2fe" emissiveIntensity={0.6} />
        </mesh>
        {/* Cursor cursor block */}
        <mesh
          position={[0.3, -0.12, 0]}
          visible={Math.floor(frame / 10) % 2 === 1}
        >
          <boxGeometry args={[0.15, 0.04, 0.02]} />
          <meshStandardMaterial color="#ffffff" />
        </mesh>
      </group>
    </group>
  );
};

// -------------------------------------------------------------
// Slide 2: Pulsating Core (Agent-Level Language)
// -------------------------------------------------------------
const PulsatingCore: React.FC = () => {
  const frame = useCurrentFrame();
  const rotationY = frame * 0.005;
  const rotationX = frame * 0.003;
  const scale = 2.2 + Math.sin(frame * 0.04) * 0.15;

  return (
    <mesh rotation={[rotationX, rotationY, 0]} scale={[scale, scale, scale]}>
      <sphereGeometry args={[1, 32, 32]} />
      <meshStandardMaterial
        color="#4facfe"
        wireframe
        emissive="#1050a0"
        emissiveIntensity={0.6}
        roughness={0.1}
        metalness={0.9}
      />
    </mesh>
  );
};

// -------------------------------------------------------------
// Slide 3: VM Pipeline Stack (AST Parser & Stack VM)
// -------------------------------------------------------------
const StackMachine: React.FC = () => {
  const frame = useCurrentFrame();
  const baseRot = frame * 0.005;

  return (
    <group rotation={[0.4, baseRot, 0.2]}>
      {[0, 1, 2, 3].map((idx) => {
        const baseY = -1.35 + idx * 0.9;
        const yOffset = Math.sin(frame * 0.05 + idx * 1.5) * 0.2;
        return (
          <mesh key={idx} position={[0, baseY + yOffset, 0]}>
            <boxGeometry args={[2.4, 0.15, 2.4]} />
            <meshStandardMaterial
              color="#3b82f6"
              roughness={0.2}
              metalness={0.8}
              emissive="#1d4ed8"
              emissiveIntensity={0.5}
            />
          </mesh>
        );
      })}
    </group>
  );
};

// -------------------------------------------------------------
// Slide 4: Secure Sandbox (Capability Guard)
// -------------------------------------------------------------
const SecureSandbox: React.FC = () => {
  const frame = useCurrentFrame();
  const rot1 = frame * 0.01;
  const rot2 = -frame * 0.008;

  return (
    <group>
      {/* Center Protected Core */}
      <mesh rotation={[0, frame * 0.005, 0]}>
        <sphereGeometry args={[1.0, 32, 32]} />
        <meshStandardMaterial
          color="#ffffff"
          roughness={0.1}
          metalness={0.9}
          emissive="#202020"
        />
      </mesh>

      {/* Outer Ring 1 */}
      <mesh rotation={[rot1, rot1 * 0.5, 0]}>
        <torusGeometry args={[1.9, 0.04, 16, 100]} />
        <meshStandardMaterial
          color="#10b981"
          emissive="#054020"
          emissiveIntensity={0.6}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>

      {/* Outer Ring 2 */}
      <mesh rotation={[Math.PI / 4, rot2, rot2 * 0.5]}>
        <torusGeometry args={[2.3, 0.04, 16, 100]} />
        <meshStandardMaterial
          color="#34d399"
          emissive="#054020"
          emissiveIntensity={0.6}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>
    </group>
  );
};

// -------------------------------------------------------------
// Slide 5: Decision Network (Agentic Primitives)
// -------------------------------------------------------------
const DecisionNetwork: React.FC = () => {
  const frame = useCurrentFrame();
  const rotOuter = frame * 0.006;
  const rotInner = -frame * 0.01;

  const nodes = useMemo(() => {
    return [
      { angleOffset: 0, axis: "xy" },
      { angleOffset: Math.PI / 2, axis: "xz" },
      { angleOffset: Math.PI, axis: "yz" },
      { angleOffset: (3 * Math.PI) / 2, axis: "xy" },
    ];
  }, []);

  return (
    <group>
      {/* Outer Network Mesh */}
      <mesh rotation={[rotOuter, rotOuter * 0.5, rotOuter * 0.2]}>
        <dodecahedronGeometry args={[2.0, 1]} />
        <meshStandardMaterial
          color="#00f2fe"
          wireframe
          emissive="#053040"
          emissiveIntensity={0.5}
        />
      </mesh>

      {/* Inner Core */}
      <mesh rotation={[0, rotInner, rotInner * 0.5]}>
        <icosahedronGeometry args={[0.9, 1]} />
        <meshStandardMaterial
          color="#ffffff"
          wireframe
          emissive="#4facfe"
          emissiveIntensity={0.4}
        />
      </mesh>

      {/* Orbiting nodes */}
      {nodes.map((node, i) => {
        const angle = frame * 0.02 + node.angleOffset;
        let pos: [number, number, number] = [0, 0, 0];
        if (node.axis === "xy") {
          pos = [Math.cos(angle) * 3, Math.sin(angle) * 3, 0];
        } else if (node.axis === "xz") {
          pos = [Math.cos(angle) * 3, 0, Math.sin(angle) * 3];
        } else {
          pos = [0, Math.cos(angle) * 3, Math.sin(angle) * 3];
        }

        return (
          <group key={i}>
            <mesh position={pos}>
              <sphereGeometry args={[0.15, 16, 16]} />
              <meshStandardMaterial color="#ffffff" emissive="#00f2fe" emissiveIntensity={0.8} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
};

// -------------------------------------------------------------
// Slide 6: PyBridge Link
// -------------------------------------------------------------
const PyBridge: React.FC = () => {
  const frame = useCurrentFrame();
  const energyPos = -2.5 + ((frame * 0.04) % 1) * 5.0;

  return (
    <group rotation={[0.2, frame * 0.003, 0]}>
      {/* Left Node (Python) */}
      <mesh position={[-2.5, 0, 0]} rotation={[frame * 0.008, frame * 0.01, 0]}>
        <boxGeometry args={[1.2, 1.2, 1.2]} />
        <meshStandardMaterial
          color="#3572A5"
          metalness={0.6}
          roughness={0.3}
          emissive="#1a3a55"
          emissiveIntensity={0.4}
        />
      </mesh>

      {/* Right Node (Inthon) */}
      <mesh position={[2.5, 0, 0]} rotation={[-frame * 0.01, 0, frame * 0.008]}>
        <octahedronGeometry args={[0.9, 0]} />
        <meshStandardMaterial
          color="#ffd43b"
          metalness={0.6}
          roughness={0.3}
          emissive="#504005"
          emissiveIntensity={0.4}
        />
      </mesh>

      {/* Bridge Beam */}
      <mesh position={[0, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.06, 0.06, 5.0, 16]} />
        <meshStandardMaterial
          color="#ffffff"
          emissive="#ffffff"
          emissiveIntensity={0.8 + Math.sin(frame * 0.1) * 0.2}
        />
      </mesh>

      {/* Energy Particle */}
      <mesh position={[energyPos, 0, 0]}>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial color="#ffffff" emissive="#ffd43b" emissiveIntensity={1.2} />
      </mesh>
    </group>
  );
};

// -------------------------------------------------------------
// Slide 7: Token Compaction (up to 76% fewer tokens)
// -------------------------------------------------------------
const TokenCompaction: React.FC = () => {
  const frame = useCurrentFrame();

  // Exponential decay function for snappy, smooth compaction ease
  const factor = Math.pow(Math.max(0, 1 - frame / 65), 3.5);

  const rot = frame * 0.01;

  return (
    <group rotation={[rot, rot * 0.5, 0]}>
      {/* Compacting floating blocks converging to the center */}
      <mesh position={[-2.2 * factor, -2.2 * factor, -2.2 * factor]}>
        <boxGeometry args={[0.6, 0.6, 0.6]} />
        <meshStandardMaterial color="#ff5f56" emissive="#401010" />
      </mesh>

      <mesh position={[2.2 * factor, -2.2 * factor, 2.2 * factor]}>
        <boxGeometry args={[0.6, 0.6, 0.6]} />
        <meshStandardMaterial color="#ffbd2e" emissive="#403005" />
      </mesh>

      <mesh position={[-2.2 * factor, 2.2 * factor, 2.2 * factor]}>
        <boxGeometry args={[0.6, 0.6, 0.6]} />
        <meshStandardMaterial color="#27c93f" emissive="#054010" />
      </mesh>

      <mesh position={[2.2 * factor, 2.2 * factor, -2.2 * factor]}>
        <boxGeometry args={[0.6, 0.6, 0.6]} />
        <meshStandardMaterial color="#00f2fe" emissive="#053040" />
      </mesh>

      {/* Central compressed core that becomes larger/brighter when items merge */}
      <mesh scale={1.2 + (1 - factor) * 0.4}>
        <octahedronGeometry args={[0.7, 0]} />
        <meshStandardMaterial
          color="#ffffff"
          roughness={0.1}
          metalness={0.9}
          emissive="#34d399"
          emissiveIntensity={1.0 - factor * 0.7}
        />
      </mesh>
    </group>
  );
};

// -------------------------------------------------------------
// Slide 8: Stellar Field (github.com/harvatechs/inthon)
// -------------------------------------------------------------
const StellarField: React.FC = () => {
  const frame = useCurrentFrame();

  const particles = useMemo(() => {
    const list = [];
    for (let i = 0; i < 80; i++) {
      list.push({
        x: (random("x-" + i) - 0.5) * 14,
        y: (random("y-" + i) - 0.5) * 8,
        zStart: random("z-" + i) * 20,
      });
    }
    return list;
  }, []);

  return (
    <group>
      {/* Central Complex Logo */}
      <mesh rotation={[frame * 0.006, frame * 0.004, frame * 0.002]}>
        <torusKnotGeometry args={[0.85, 0.25, 100, 16]} />
        <meshStandardMaterial
          color="#ffffff"
          metalness={0.9}
          roughness={0.1}
          emissive="#4facfe"
          emissiveIntensity={0.7}
        />
      </mesh>

      {/* Flying particles */}
      {particles.map((p, i) => {
        const z = ((p.zStart + frame * 0.08) % 20) - 10;
        return (
          <mesh key={i} position={[p.x, p.y, z]}>
            <boxGeometry args={[0.08, 0.08, 0.08]} />
            <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
          </mesh>
        );
      })}
    </group>
  );
};

// -------------------------------------------------------------
// Main Canvas Orchestrator
// -------------------------------------------------------------
export const ThreeDScene: React.FC<ThreeDSceneProps> = ({
  slideIndex,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  // Overall slide fade effects
  const groupOpacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // Camera zoom in/out effect
  const scale = interpolate(frame, [0, durationInFrames], [0.9, 1.1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        opacity: groupOpacity,
        zIndex: 5,
        backgroundColor: "#000000",
      }}
    >
      <ThreeCanvas width={1920} height={1080}>
        <ambientLight intensity={0.12} />
        <pointLight position={[8, 8, 8]} intensity={1.5} color="#4facfe" />
        <pointLight position={[-8, -8, -8]} intensity={0.8} color="#00f2fe" />
        <directionalLight position={[0, 4, 4]} intensity={0.6} color="#ffffff" />

        <group scale={[scale, scale, scale]}>
          {slideIndex === 0 && <TerminalShell />}
          {slideIndex === 1 && <PulsatingCore />}
          {slideIndex === 2 && <StackMachine />}
          {slideIndex === 3 && <SecureSandbox />}
          {slideIndex === 4 && <DecisionNetwork />}
          {slideIndex === 5 && <PyBridge />}
          {slideIndex === 6 && <TokenCompaction />}
          {slideIndex === 7 && <StellarField />}
        </group>
      </ThreeCanvas>
    </div>
  );
};
