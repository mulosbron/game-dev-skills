---
name: colyseus
description: Authoritative Node.js and TypeScript multiplayer framework (v0.18). Use when implementing Colyseus servers, Rooms, @colyseus/schema state sync, matchmaking/presence/drivers, client-side prediction and lag compensation, or TS/React/Unity/Godot/GameMaker/Defold SDK clients.
---

# Colyseus

Authoritative multiplayer server and client framework (`colyseus` v0.18.12, `@colyseus/core` v0.18.28, `@colyseus/sdk` v0.18.10, `@colyseus/schema` ^5.0.8, MIT, Node.js `>= 22.x`).

- **Quickstart**: `npm create colyseus-app@latest ./my-server`
- **Dev & testing**: Vite HMR via `colyseus/vite`; inject artificial network delay with `server.simulateLatency(ms)` or `COLYSEUS_LATENCY`.

## Server & Configuration

Configure rooms and HTTP routes with `defineServer` / `defineRoom` (or `new Server(options)` + `server.define()`), or `@colyseus/tools` `config(...)` + `listen(...)`:

```ts
import { defineServer, defineRoom } from "colyseus";
import { MyRoom } from "./MyRoom.js";

const server = defineServer({
  rooms: { my_room: defineRoom(MyRoom, { maxClients: 8 }) },
  // presence: new RedisPresence(...), driver: new RedisDriver(...)
});
await server.listen(2567); // or await server.serverless()
```

- **`ServerOptions`** (`@colyseus/core`): `publicAddress`, `presence`, `driver`, `transport`, `gracefullyShutdown`, `beforeListen`, `database`, `auth`, `express`, `selectProcessIdToCreateRoom`, `isStandaloneMatchMaker`, `devMode`, `greet`.
- **Built-in rooms**:
  - `LobbyRoom`: subscribes clients to public room updates (`"rooms"`, `"+"`, `"-"`).
  - `RelayRoom`: relays `"*"` messages (`maxClients`, `allowReconnectionTime` capped at 40s).
  - `QueueRoom`: ranked/grouped queue (`QueueOptions`: `maxPlayers`, `matchRoomName`, `maxWaitingCycles`, `maxWaitingCyclesForPriority`, `maxTeamSize`, `allowIncompleteGroups`, `compare`, `onGroupReady`).
- **Built-in room plugins** (`definePlugins([...])`): `TrackUserSessionsPlugin` (`colyseus/plugins/track-user-sessions`), `AnalyticsPlugin`, `CloudSavesPlugin`, `LeaderboardsPlugin` (`@colyseus/database`), plus `colyseus/plugins/webrtc`, `colyseus/plugins/idle-kick`, `colyseus/plugins/unique-session`.

## Room Lifecycle & Messaging

Type a room with `class MyRoom extends Room<{ state: MyState; client: MyClient; metadata: Meta; input: Input }>`.

| Hook / Method | Purpose & Notes |
|---|---|
| `onCreate(options)` | Initialize state (`setState`), handlers, and simulation loops |
| `onAuth(client, options, context)` | Validate joining client (or `static async onAuth(...)`; `import "@colyseus/auth"` installs JWT-decoding default) |
| `onJoin(client, options, auth)` | Spawn player state and attach client |
| `onDrop(client, code)` / `onReconnect(client)` | Handle transient drop; call `this.allowReconnection(client, seconds \| "manual")` unless `code === CloseCode.CONSENTED` |
| `onLeave(client, code)` | Final cleanup after disconnect or missed reconnection window |
| `onBeforePatch(state)` / `onDispose()` | Pre-patch hook and room teardown |
| `onUncaughtException(error, methodName)` | Handle room hook errors |
| `onUnhandledMessage(client, type, message)` | Catch unregistered client message types |
| `onCacheRoom()` / `onRestoreRoom(cached)` | Persist/restore room state when `devMode: true` |

- **Matchmaking visibility**: Use `this.setMatchmaking({ metadata, private, locked, maxClients, unlisted })` (plus `setMetadata`, `setPrivate`, `lock()`, `unlock()`). `metadata` is **replaced**, not merged (spread `{ ...this.metadata, ... }`), and assigning `this.metadata = ...` directly throws `ServerError` outside `onCreate()`.
- **Messages**: Register handlers with `this.onMessage(type, [validationSchema,] handler)` (supports Standard Schema e.g. `zod`, and `"*"` wildcard), `this.onMessageBytes(...)`, or declarative `messages = { key: validate(zodSchema, handler) }`. Send via `client.send(type, msg)`, `this.broadcast(type, msg, { except })`, `this.broadcastBytes(...)`, or `this.batchMessages(() => ...)`.
- **Simulation ticks**: Prefer `this.setFixedTimestep((ctx: StepContext) => ..., tickRate = 60, { subSteps })` (`ctx`: `dt`, `dtMs`, `tick`, `subSteps`, `subDt`, `subDtMs`), or `this.setTimestep(cb, delay)` (`setSimulationInterval` is deprecated). Control state sync cadence via `patchRate` (default `1000/20` = 50ms) and `unreliablePatchRate`.

## `@colyseus/schema` v5 State Sync

Define state using either the v5 functional API or decorators (`Schema`, `MapSchema`, `ArraySchema`, `SetSchema`):

```ts
import { schema, t, type SchemaType } from "@colyseus/schema";

const Player = schema({ x: t.number(), y: t.number(), dir: t.int8<-1 | 0 | 1>() });
type Player = SchemaType<typeof Player>;
const MyState = schema({ players: t.map(Player) });
```

- **Decorator alternative**: `class State extends Schema { @type({ map: Player }) players = new MapSchema<Player>(); @type("number") score: number; }`.
- **Unreliable patches**: `@unreliable` excludes a field from reliable `broadcastPatch()` and sends it over `H3Transport` datagrams (flushes inline after `broadcastPatch()` unless `unreliablePatchRate` configures a dedicated timer; `unknown refId` on out-of-order datagrams is routine).
- **Client callbacks** (`@colyseus/sdk`): Use `const $ = getStateCallbacks(room)` (or `Callbacks.get(room)`): `$(room.state).players.onAdd((p, sid) => ...)`, `.onRemove(...)`, `$.listen(p, "x", val => ...)`, and `room.onStateChange`.

## Matchmaking, Presence & Drivers

| Layer | Default (Single Process) | Horizontal / Production Options |
|---|---|---|
| Transport | `WebSocketTransport` (`@colyseus/ws-transport`) | `uWebSocketsTransport` (`@colyseus/uwebsockets-transport`), `@colyseus/bun-websockets`, `H3Transport` (`@colyseus/h3-transport`, experimental WebTransport for datagrams) |
| Presence | `LocalPresence` | `RedisPresence` (`@colyseus/redis-presence`) |
| Matchmaking Driver | `LocalDriver` | `RedisDriver` (`@colyseus/redis-driver`), `PostgresDriver` (`@colyseus/drizzle-driver`), `MongooseDriver` (`@colyseus/mongoose-driver`), `DatabaseDriver` (`@colyseus/database`) |

Server-side `matchMaker` API (`@colyseus/core`): `joinOrCreate`, `create`, `join`, `joinById`, `reconnect`, `query`, `findRoomsByIds`, `findOneRoomAvailable`, `remoteRoomCall`, `reserveSeatFor`.

## Client Prediction & Lag Compensation (0.18)

For full rollback, sim, rewind, and divergence diagnostics, read [PREDICTION.md](references/PREDICTION.md).

- **Server inputs & rewind**:
  - `this.defineInput(MoveInput, { bufferMaxSize: 32, seqField, sanitize, idle })` (`sanitize` modifies in place NaN-safely; `idle` synthesizes idle frames without advancing `lastProcessed` ack; never `{ ...latest }` spread a schema instance). Consume via `this.inputs.get(sid).drain()` / `for (const cmd of this.inputs.get(sid))` (per-entity) or `.next()` (shared physics).
  - Arm lag-comp rewind: `this.rewind = this.allowRewindState({ maxRewindMs: 500 })`; `this.rewind.attachAll(this.state.players, { fields: ["x", "y"], mode: "snapshot" | "reckon", interpolate })`; query hit-tests via `const seen = this.rewind.lastSeenBy(shooterId)` -> `seen.value(target, "x")` / `seen.read(target, fields, out)`.
- **Client prediction** (`@colyseus/sdk/predict` or `@colyseus/sdk`):
  - `const predict = Predict.get(room, { mode: "lerp" | "extrapolate" | "damped" | "reckon", delay: 100 })`
  - `predict.attachAll("players", { mode: "lerp", fields: ["x", "y"], snap: 4 })`
  - `const input = room.input({ mode: "reliable" | "unreliable" })`
  - Local rollback: `predict.reconciler(self, { input, step: (ctx, s, cmd) => ..., smoothing, fields, warnOnDivergence })` or composite `predict.sim({ input, world, step, adopt, pose })`; plus `predict.defineEvent(...)` (`PredictedEventChannel`) and `predict.spawns(...)` (`PredictedSpawns`).
  - `room.clock` is always non-null (`NULL_CLOCK` stub pre-handshake or without `defineInput()`): `serverNow()`, `renderNow()`, `smoothedRtt()`, `rtt()`, `jitter()`, `lastServerTime()`.
- **Load-bearing frame order**: Call `const n = predict.tick(now)` -> loop `n` times latching/consuming buttons (`input.data...; input.send()`) -> only THEN read `predict.value(e, field)` / `predict.read(...)`. Keep inputs flat primitives. Inspect `me.drift.ema` vs `me.drift.peak` and `import "@colyseus/sdk/debug"` (`__net(delay, jitter)`).

## Client & Engine SDKs

- **TypeScript / JS**: `npm install @colyseus/sdk`. `const client = new Client<typeof server>(url, { protocol?: "ws" | "h3" })` (`ColyseusSDK` alias): `joinOrCreate`, `create`, `join`, `joinById`, `reconnect(token)`, `consumeSeatReservation`, `getLatency()`, typed `client.http.get/post/put/patch/delete`. `Room` supports `onMessage`, `send`, `request` (Promise RPC), `sendUnreliable`, `sendBytes`, `onDrop`, `onReconnect`, `onLeave`, `leave()`.
- **React**: `npm install @colyseus/react`.
- **Engine SDKs**: Unity (`Colyseus_Plugin.unitypackage`), Godot (`colyseus/native-sdk` releases), GameMaker (`colyseus/native-sdk` releases), Defold, Construct 3, Haxe (`haxelib install colyseus`), and C Static Libraries (`native-sdk`). See [PORTING.md](references/PORTING.md) for cross-SDK contract rules (e.g., `now` is optional in JS/Defold/Unity/Haxe/Flutter/Godot — negative sentinel in GDScript — but required in C/GameMaker).

## References

- [PREDICTION.md](references/PREDICTION.md) — Full Colyseus 0.18 client-side prediction, rollback, events, spawns, and lag compensation guide
- [PORTING.md](references/PORTING.md) — 0.18 multi-engine SDK porting contract and manifest (C#, C, Lua, Haxe, Defold, Unity, Godot, GameMaker)
- [AGENTS.md](references/AGENTS.md) — Monorepo build and test commands
