import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/* All board coordinates come from the validated planar geometry in PCB_ART_DATA.
   Units are mm. A front surface is z = -index * (thickness + gap + explode).
   ENIG is a flat material map; it never adds geometry or height. */
const $ = (id) => document.getElementById(id);
const data = globalThis.PCB_ART_DATA;
const spec = data?.spec;
const designMap = new Map((data?.designs || []).map((design) => [design.id, design]));
const GOLD = '#d9b45d';
const FACE_PX = 13;
const state = {
  ready: false,
  designId: null,
  variantId: null,
  visibleCount: 0,
  isolatedLayer: null,
  explode: 0,
  view: 'iso',
  artwork: true,
  hardware: true,
  rails: false,
  section: false,
};
let scene, camera, renderer, controls, pmrem, envTarget, observer;
let design = null;
let designGroup = null;
let railGroup = null;
let hardwareGroup = null;
let panelGroups = [];
let screwColumns = [];
let materialSet = new Set();
let renderFrame = null;
let toastTimer = null;
let lastWidth = 0;
let lastHeight = 0;
let fitPending = false;
let programmaticCamera = false;
let initFailed = false;
let directionalLight;
const viewport = $('viewport');
const clip = spec ? new THREE.Plane(new THREE.Vector3(-1, 0, 0), spec.width / 2) : null;
const VIEWS = {
  iso: [0.68, -0.48, 1.34],
  front: [0, 0, 1],
  side: [1, 0, 0],
  back: [0, 0, -1],
};
const fmt = (n, places = 1) => Number(n).toFixed(places);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const showToast = (message) => {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3500);
};

function material(options) {
  const m = new THREE.MeshPhysicalMaterial({ specularIntensity: 0.28, ...options });
  m.clippingPlanes = state.section ? [clip] : [];
  m.clipShadows = true;
  materialSet.add(m);
  return m;
}

function drawPolygon(ctx, pts, close = true) {
  if (!pts?.length) return;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  if (close) ctx.closePath();
}

function layerFinish(layer) {
  if (['enig-art', 'enig-fill', 'mask-only'].includes(layer.finish)) return layer.finish;
  if (layer.surface === 'gold') return 'enig-fill';
  return (layer.art?.fills?.length || layer.art?.strokes?.length) ? 'enig-art' : 'mask-only';
}

function finishLabel(layer) {
  if (layer.finishLabel) return layer.finishLabel;
  return { 'enig-art': 'ENIG art', 'enig-fill': 'Full ENIG', 'mask-only': 'No exposed copper' }[layerFinish(layer)];
}

function finishSummary() {
  const summary = { enigLayers: [], maskOnlyLayers: [], enigCount: 0, maskOnlyCount: 0, totalLayers: design?.layers.length || 0 };
  design?.layers.forEach((layer, index) => {
    (layerFinish(layer) === 'mask-only' ? summary.maskOnlyLayers : summary.enigLayers).push(index + 1);
  });
  summary.enigCount = summary.enigLayers.length;
  summary.maskOnlyCount = summary.maskOnlyLayers.length;
  // Derive from the per-layer policy so older files without finishSummary work
  // and the labels always describe the same boards that are actually rendered.
  return summary;
}

function makeArtwork(layer) {
  if (layerFinish(layer) === 'mask-only') return null;
  const colorCanvas = document.createElement('canvas');
  const ormCanvas = document.createElement('canvas');
  colorCanvas.width = ormCanvas.width = Math.round(spec.width * FACE_PX);
  colorCanvas.height = ormCanvas.height = Math.round(spec.height * FACE_PX);
  const c = colorCanvas.getContext('2d');
  const o = ormCanvas.getContext('2d');
  const sx = colorCanvas.width / spec.width;
  const sy = colorCanvas.height / spec.height;
  for (const ctx of [c, o]) {
    ctx.setTransform(sx, 0, 0, sy, 0, 0);
    ctx.lineJoin = design.artStyle === 'angular' ? 'miter' : 'round';
    ctx.lineCap = design.artStyle === 'angular' ? 'butt' : 'round';
    ctx.miterLimit = 10;
  }
  c.fillStyle = layerFinish(layer) === 'enig-fill' ? GOLD : layer.mask;
  c.fillRect(0, 0, spec.width, spec.height);
  // The green channel controls roughness; blue controls metalness.
  o.fillStyle = layerFinish(layer) === 'enig-fill' ? 'rgb(0,88,255)' : 'rgb(0,153,0)';
  o.fillRect(0, 0, spec.width, spec.height);
  const style = (ctx, color, orm) => {
    const isGold = !color;
    const value = orm ? (isGold ? 'rgb(0,88,255)' : 'rgb(0,153,0)') : (color || GOLD);
    ctx.fillStyle = value;
    ctx.strokeStyle = value;
  };
  for (const fill of layer.art?.fills || []) {
    for (const [ctx, orm] of [[c, false], [o, true]]) {
      style(ctx, fill.color, orm);
      drawPolygon(ctx, fill.pts);
      ctx.fill();
    }
  }
  for (const stroke of layer.art?.strokes || []) {
    for (const [ctx, orm] of [[c, false], [o, true]]) {
      style(ctx, stroke.color, orm);
      ctx.lineWidth = stroke.w || 0.3;
      drawPolygon(ctx, stroke.pts, stroke.closed === true);
      ctx.stroke();
    }
  }
  const colorMap = new THREE.CanvasTexture(colorCanvas);
  colorMap.colorSpace = THREE.SRGBColorSpace;
  const ormMap = new THREE.CanvasTexture(ormCanvas);
  const anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
  for (const texture of [colorMap, ormMap]) {
    // ShapeGeometry produces unnormalised XY UVs. The canvas top maps to +Y.
    texture.repeat.set(1 / spec.width, 1 / spec.height);
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.anisotropy = anisotropy;
  }
  return { colorMap, ormMap, strokeJoin: c.lineJoin, strokeCap: c.lineCap };
}

function makeShape(layer) {
  const toXY = ([x, y]) => new THREE.Vector2(x, spec.height - y);
  const outer = layer.outer.map(toXY);
  // Three's extrusion normalises winding internally; explicit winding also
  // keeps its triangulation path unambiguous for the more complex coral holes.
  if (!THREE.ShapeUtils.isClockWise(outer)) outer.reverse();
  const shape = new THREE.Shape(outer);
  for (const polygon of layer.holes || []) {
    const points = polygon.map(toXY);
    if (THREE.ShapeUtils.isClockWise(points)) points.reverse();
    shape.holes.push(new THREE.Path(points));
  }
  return shape;
}

function makePanel(layer) {
  const group = new THREE.Group();
  group.name = `layer-${layer.index + 1}`;
  const shape = makeShape(layer);
  const bodyGeometry = new THREE.ExtrudeGeometry(shape, {
    depth: spec.thickness,
    bevelEnabled: false,
    curveSegments: 8,
    steps: 1,
  });
  bodyGeometry.translate(0, 0, -spec.thickness);
  const mask = material({ color: layer.mask, roughness: 0.60, metalness: 0 });
  const edge = material({ color: '#b7a779', roughness: 0.8, metalness: 0 });
  const body = new THREE.Mesh(bodyGeometry, [mask, edge]);
  body.castShadow = body.receiveShadow = true;
  group.userData.body = body;
  group.userData.index = layer.index;
  group.userData.finish = layerFinish(layer);
  group.add(body);
  const artwork = makeArtwork(layer);
  if (artwork) {
    const { colorMap, ormMap, strokeJoin, strokeCap } = artwork;
    const artMaterial = material({
      map: colorMap,
      roughnessMap: ormMap,
      metalnessMap: ormMap,
      metalness: 1,
      roughness: 1,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
    });
    const face = new THREE.Mesh(new THREE.ShapeGeometry(shape, 8), artMaterial);
    face.name = 'flat-enig-artwork';
    // The offset only prevents depth fighting; the underlying board remains 1.6 mm.
    face.position.z = 0.006;
    face.receiveShadow = true;
    face.visible = state.artwork;
    face.userData.strokeJoin = strokeJoin;
    face.userData.strokeCap = strokeCap;
    group.userData.face = face;
    group.add(face);
  }
  return group;
}

function alongZ(geometry) {
  geometry.rotateX(Math.PI / 2);
  return geometry;
}

function makeHardware() {
  hardwareGroup = new THREE.Group();
  hardwareGroup.name = 'M3-hardware';
  const steel = material({ color: '#c8cccf', metalness: 1, roughness: 0.27 });
  const steelDark = material({ color: '#51565a', metalness: 0.75, roughness: 0.4 });
  const brass = material({ color: '#c3a365', metalness: 1, roughness: 0.38 });
  const headGeometry = alongZ(new THREE.CylinderGeometry(2.75, 2.75, 2.2, 32));
  const shaftGeometry = alongZ(new THREE.CylinderGeometry(1.45, 1.45, 1, 16));
  const nutGeometry = alongZ(new THREE.CylinderGeometry(5.5 / Math.sqrt(3), 5.5 / Math.sqrt(3), 2.4, 6));
  const spacerGeometry = alongZ(new THREE.CylinderGeometry(spec.spacerOD / 2, spec.spacerOD / 2, spec.gap, 24));
  // Dark hexagon inset is flush with the head's face, not a protruding part.
  const socketGeometry = new THREE.CircleGeometry(1.19, 6);
  socketGeometry.rotateZ(Math.PI / 6);
  screwColumns = spec.screws.map(([x, y]) => {
    const column = new THREE.Group();
    column.position.set(x, spec.height - y, 0);
    const head = new THREE.Mesh(headGeometry, steel);
    head.position.z = 1.1;
    const socket = new THREE.Mesh(socketGeometry, steelDark);
    socket.position.z = 2.207;
    const shaft = new THREE.Mesh(shaftGeometry, steel);
    const nut = new THREE.Mesh(nutGeometry, steel);
    const spacers = Array.from({ length: design.layers.length - 1 }, () => new THREE.Mesh(spacerGeometry, brass));
    for (const part of [head, socket, shaft, nut, ...spacers]) {
      part.castShadow = true;
      part.receiveShadow = true;
      column.add(part);
    }
    hardwareGroup.add(column);
    return { head, socket, shaft, nut, spacers };
  });
  designGroup.add(hardwareGroup);
}

function makeRails() {
  railGroup = new THREE.Group();
  railGroup.name = 'reference-rail-envelope';
  const railMaterial = material({
    color: '#727b84', metalness: 0.45, roughness: 0.62,
    transparent: true, opacity: 0.32, depthWrite: false,
  });
  const railHeight = spec.railTall || 12.59;
  const railDepth = spec.railDeep || 20.13;
  const topSlotY = spec.slots?.[0]?.[1] || 2.87;
  const beyondEdge = (spec.railNutFromOuter || 6.37) - topSlotY;
  for (const upper of [true, false]) {
    const geometry = new THREE.BoxGeometry(spec.width + 36, railHeight, railDepth);
    const box = new THREE.Mesh(geometry, railMaterial);
    const centerY = upper ? -beyondEdge + railHeight / 2 : spec.height + beyondEdge - railHeight / 2;
    box.position.set(spec.width / 2, spec.height - centerY, -spec.thickness - railDepth / 2);
    box.renderOrder = 2;
    railGroup.add(box);
  }
  designGroup.add(railGroup);
}

function disposeDesign() {
  if (!designGroup) return;
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();
  designGroup.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    for (const mat of Array.isArray(object.material) ? object.material : [object.material]) {
      if (!mat) continue;
      materials.add(mat);
      for (const value of Object.values(mat)) if (value?.isTexture) textures.add(value);
    }
  });
  scene.remove(designGroup);
  geometries.forEach((geometry) => geometry.dispose());
  textures.forEach((texture) => {
    texture.dispose();
    if (texture.image instanceof HTMLCanvasElement) {
      texture.image.width = 1;
      texture.image.height = 1;
    }
  });
  materials.forEach((mat) => mat.dispose());
  materialSet.clear();
  panelGroups = [];
  screwColumns = [];
  designGroup = null;
  hardwareGroup = null;
  railGroup = null;
  renderer.renderLists.dispose();
}

function displayedIndices() {
  if (!design) return [];
  if (state.isolatedLayer !== null) return [state.isolatedLayer];
  return design.layers.map((_, index) => index).filter((index) => index < state.visibleCount);
}

function updateModel() {
  if (!designGroup) return;
  const pitch = spec.thickness + spec.gap + state.explode;
  const indices = displayedIndices();
  panelGroups.forEach((group, index) => {
    group.position.z = -index * pitch;
    group.visible = indices.includes(index);
    if (group.userData.face) group.userData.face.visible = state.artwork;
  });
  const lastIndex = state.visibleCount - 1;
  const backZ = -lastIndex * pitch - spec.thickness;
  for (const column of screwColumns) {
    // In the exploded view the spacers retain their physical 3 mm height.
    // Long shafts disappear to avoid suggesting an actual telescoping screw.
    const shaftLength = state.visibleCount * spec.thickness + (state.visibleCount - 1) * spec.gap + 3.8;
    column.shaft.scale.z = shaftLength;
    column.shaft.position.z = -shaftLength / 2;
    column.shaft.visible = state.explode === 0;
    column.nut.position.z = backZ - 1.2;
    column.nut.visible = state.visibleCount > 1;
    column.spacers.forEach((spacer, index) => {
      spacer.visible = index < lastIndex;
      spacer.position.z = -index * pitch - spec.thickness - (spec.gap + state.explode) / 2;
    });
  }
  hardwareGroup.visible = state.hardware && state.isolatedLayer === null;
  railGroup.visible = state.rails;
  for (const m of materialSet) {
    const changed = Boolean(m.clippingPlanes?.length) !== state.section;
    m.clippingPlanes = state.section ? [clip] : [];
    if (changed) m.needsUpdate = true;
  }
  updateStateUI();
  requestRender();
}

function visibleBounds() {
  const indices = displayedIndices();
  const pitch = spec.thickness + spec.gap + state.explode;
  const first = Math.min(...indices);
  const last = Math.max(...indices);
  const hasFront = indices.includes(0);
  const lowerY = hasFront ? 0 : spec.keepout;
  const upperY = hasFront ? spec.height : spec.height - spec.keepout;
  return new THREE.Box3(
    new THREE.Vector3(0, lowerY, -last * pitch - spec.thickness),
    new THREE.Vector3(spec.width, upperY, -first * pitch + 2.2),
  );
}

function fitCamera(direction = null) {
  if (!camera || !design) return;
  const bounds = visibleBounds();
  const center = bounds.getCenter(new THREE.Vector3());
  const dir = direction ? new THREE.Vector3(...direction).normalize() : camera.position.clone().sub(controls.target).normalize();
  if (dir.lengthSq() < 0.01) dir.set(...VIEWS.iso).normalize();
  const right = new THREE.Vector3().crossVectors(camera.up, dir).normalize();
  if (right.lengthSq() < 0.01) right.set(1, 0, 0);
  const up = new THREE.Vector3().crossVectors(dir, right).normalize();
  const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const aspect = viewport.clientWidth / Math.max(viewport.clientHeight, 1);
  camera.aspect = aspect;
  camera.updateProjectionMatrix();
  const tanH = tanV * aspect;
  let distance = 1;
  for (const x of [bounds.min.x, bounds.max.x]) {
    for (const y of [bounds.min.y, bounds.max.y]) {
      for (const z of [bounds.min.z, bounds.max.z]) {
        const offset = new THREE.Vector3(x, y, z).sub(center);
        const front = offset.dot(dir);
        distance = Math.max(distance, front + Math.abs(offset.dot(up)) / tanV, front + Math.abs(offset.dot(right)) / tanH);
      }
    }
  }
  // Leave room above and below the object for the stage title and controls.
  const padding = viewport.clientWidth <= 760 ? 1.26 : 1.23;
  distance *= padding;
  programmaticCamera = true;
  camera.up.set(0, 1, 0);
  camera.position.copy(center).addScaledVector(dir, distance);
  controls.target.copy(center);
  controls.minDistance = 45;
  controls.maxDistance = 1000;
  controls.update();
  programmaticCamera = false;
  requestRender();
}

function setView(name) {
  if (!VIEWS[name] || !design) return;
  state.view = name;
  fitCamera(VIEWS[name]);
  updateViewUI();
}

function requestRender() {
  if (!renderer || initFailed || renderFrame !== null) return;
  renderFrame = requestAnimationFrame(() => {
    renderFrame = null;
    const width = Math.max(1, viewport.clientWidth);
    const height = Math.max(1, viewport.clientHeight);
    if (lastWidth !== width || lastHeight !== height) {
      const hadSize = lastWidth > 0;
      lastWidth = width;
      lastHeight = height;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (hadSize) fitPending = true;
    }
    if (fitPending && design) {
      fitPending = false;
      fitCamera();
    }
    renderer.render(scene, camera);
    if (!state.ready && design) {
      state.ready = true;
      $('loading').hidden = true;
    }
  });
}

function layerDisplayName(layer) {
  if (layerFinish(layer) === 'enig-fill') return 'Gold / black board';
  return layer.nameJa || layer.name;
}

function swatchBackground(layer) {
  return layerFinish(layer) === 'enig-fill'
    ? 'linear-gradient(120deg,#9b773c 0%,#ddbd72 36%,#f0dca1 52%,#bb924b 100%)'
    : layer.mask;
}

function variantsFor(id) {
  const family = designMap.get(id);
  return family ? [family, ...(family.variants || [])] : [];
}

function resolveDesign(id, variantId) {
  const family = designMap.get(id);
  if (!family) return null;
  const options = variantsFor(id);
  const requested = variantId ?? family.defaultVariant;
  return options.find((item) => item.variantId === requested) || family;
}

function updateVariantUI() {
  const options = variantsFor(state.designId);
  const hasVariants = options.length > 1;
  $('variant-selector').hidden = !hasVariants;
  $('variant-options').replaceChildren();
  if (!hasVariants) return;
  for (const option of options) {
    const button = el('button', 'variant-button', option.variantLabel || option.variantId);
    button.type = 'button';
    button.dataset.variant = option.variantId;
    button.setAttribute('aria-pressed', String(option.variantId === state.variantId));
    button.addEventListener('click', () => setVariant(option.variantId));
    $('variant-options').append(button);
  }
}

function populateDesignUI() {
  $('design-number').textContent = design.number;
  $('design-name').textContent = design.name;
  const variantCaption = variantsFor(state.designId).length > 1 ? ` · ${design.variantLabel || state.variantId}` : '';
  $('design-subtitle').textContent = (design.subtitle || '') + variantCaption;
  updateVariantUI();
  $('design-description').textContent = design.description || '';
  $('badge-layers').textContent = design.layers.length;
  $('badge-depth').textContent = fmt(design.stackDepth);
  const finishes = finishSummary();
  $('finish-summary').replaceChildren(
    el('span', 'finish-summary-enig', `ENIG ${finishes.enigCount} boards`),
    el('span', 'finish-summary-divider', ' / '),
    el('span', '', `No exposed copper ${finishes.maskOnlyCount} boards`),
  );
  $('finish-summary').dataset.enigCount = finishes.enigCount;
  $('finish-summary').dataset.maskOnlyCount = finishes.maskOnlyCount;
  document.title = `${design.name}${variantCaption} · PCB Art Collection · Takazudo Modular`;
  $('visible-layers').max = design.layers.length;
  $('palette-strip').replaceChildren();
  $('layer-list').replaceChildren();
  for (const [index, layer] of design.layers.entries()) {
    const chip = el('span', 'palette-chip');
    chip.style.background = swatchBackground(layer);
    chip.title = `${index + 1}. ${layerDisplayName(layer)} / ${finishLabel(layer)}`;
    chip.dataset.layer = index;
    $('palette-strip').append(chip);
    const button = el('button', 'layer-button');
    button.type = 'button';
    button.dataset.layer = index;
    button.dataset.finish = layerFinish(layer);
    button.setAttribute('aria-pressed', 'false');
    button.title = `${index + 1} layer: ${layerDisplayName(layer)} / ${finishLabel(layer)} — show alone`;
    button.setAttribute('aria-label', button.title);
    const swatch = el('span', 'layer-swatch');
    swatch.style.background = swatchBackground(layer);
    const role = index === 0 ? 'TOP' : (layer.solid || index === design.layers.length - 1) ? 'FLOOR' : '';
    const copy = el('span', 'layer-copy');
    const finish = el('span', `layer-finish${layerFinish(layer) === 'mask-only' ? ' mask-only' : ''}`, finishLabel(layer));
    finish.dataset.finish = layerFinish(layer);
    copy.append(el('span', 'layer-name', layerDisplayName(layer)), finish);
    button.append(el('span', 'layer-index', String(index + 1).padStart(2, '0')), swatch,
      copy, el('span', 'layer-role', role), el('span', 'layer-arrow', '↗'));
    button.addEventListener('click', () => isolateLayer(state.isolatedLayer === index ? null : index));
    $('layer-list').append(button);
  }
  $('design-notes').replaceChildren(...(design.notes || []).map((note) => el('li', '', note)));
  const dimensions = [
    ['Panel width × height', `${fmt(spec.width)} × ${fmt(spec.height)} mm`],
    ['Lower board height', `${fmt(spec.height - 2 * spec.keepout)} mm`],
    ['Board thickness / layer gap', `${fmt(spec.thickness)} / ${fmt(spec.gap)} mm`],
    ['Assembled stack depth', `${fmt(design.stackDepth)} mm`],
    ['Stack depth calculation', `${design.layers.length} × ${spec.thickness} + ${design.layers.length - 1} × ${spec.gap}`],
    ['Lower board rail clearance', `${fmt(spec.keepout)} mm`],
    ['Mount hole / spacer outside diameter', `Ø${fmt(spec.screwDiameter)} / Ø${fmt(spec.spacerOD)} mm`],
    ['ENIG layers', finishes.enigLayers.length ? `${finishes.enigLayers.join(', ')} layers (${finishes.enigCount} boards)` : 'none'],
    ['Layers without exposed copper', finishes.maskOnlyLayers.length ? `${finishes.maskOnlyLayers.join(', ')} layers (${finishes.maskOnlyCount} boards)` : 'none'],
  ];
  $('dimensions').replaceChildren(...dimensions.map(([label, value]) => {
    const tr = el('tr');
    tr.append(el('td', '', label), el('td', '', value));
    return tr;
  }));
  $('model-checks').replaceChildren(...(design.checks || []).map((check) => {
    const item = el('div', `model-check${check.ok ? '' : ' failed'}`);
    if (check.detail) item.title = check.detail;
    item.append(el('span', '', check.ok ? '✓' : '△'), el('span', '', check.label));
    return item;
  }));
  $('design-sources').replaceChildren(...(design.sources || []).map((source) => {
    const a = el('a', '', source.label);
    if (/^https?:\/\//.test(source.url)) {
      a.href = source.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    }
    return a;
  }));
  document.querySelectorAll('.design-tab').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.design === design.id));
    if (button.dataset.design === design.id) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
}

function updateViewUI() {
  document.querySelectorAll('[data-view]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.view === state.view));
  });
}

function updateStateUI() {
  if (!design) return;
  const n = design.layers.length;
  $('explode').value = state.explode;
  $('explode').style.setProperty('--progress', `${state.explode / 12 * 100}%`);
  $('explode-output').textContent = `+${Number.isInteger(state.explode) ? state.explode : fmt(state.explode)} mm`;
  $('visible-layers').value = state.visibleCount;
  $('visible-layers').style.setProperty('--progress', `${(state.visibleCount - 1) / Math.max(1, n - 1) * 100}%`);
  $('visible-output').textContent = state.isolatedLayer === null ? `${state.visibleCount} / ${n} layers` : `${state.isolatedLayer + 1} only`;
  for (const key of ['artwork', 'hardware', 'rails', 'section']) $(key).checked = state[key];
  const indices = displayedIndices();
  document.querySelectorAll('.layer-button').forEach((button) => {
    const index = Number(button.dataset.layer);
    button.setAttribute('aria-pressed', String(state.isolatedLayer === index));
    button.classList.toggle('is-hidden', !indices.includes(index));
  });
  document.querySelectorAll('.palette-chip').forEach((chip) => {
    const index = Number(chip.dataset.layer);
    chip.classList.toggle('is-muted', !indices.includes(index));
    chip.classList.toggle('is-selected', state.isolatedLayer === index);
  });
  const status = $('stage-status');
  status.classList.toggle('is-exploded', state.explode > 0 && state.isolatedLayer === null);
  status.classList.toggle('is-isolated', state.isolatedLayer !== null);
  let statusText = state.isolatedLayer !== null
    ? `${state.isolatedLayer + 1} layer / isolated`
    : state.explode > 0 ? `Exploded view +${state.explode} mm` : 'Assembled';
  if (state.isolatedLayer === null && state.visibleCount < n) statusText += ` · ${state.visibleCount} layers`;
  if (state.section) statusText += ' · section';
  status.querySelector('span').textContent = statusText;
  $('rail-note').hidden = !state.rails;
  if (state.isolatedLayer !== null) {
    const layer = design.layers[state.isolatedLayer];
    const position = state.isolatedLayer === 0 ? 'Top panel' : layer.solid ? 'Back floor board' : `Layer ${state.isolatedLayer + 1}`;
    const finishNote = layerFinish(layer) === 'mask-only'
      ? 'This layer has no exposed copper.'
      : layerFinish(layer) === 'enig-fill' ? 'ENIG covers much of this black board.' : 'This layer uses ENIG art.';
    $('layer-note').textContent = `${position}: ${finishNote}${layer.note ? ` ${layer.note}` : ''}`;
    $('layer-note').hidden = false;
  } else $('layer-note').hidden = true;
  updateViewUI();
}

function installDesign(next) {
  state.ready = false;
  disposeDesign();
  design = next;
  state.designId = design.id;
  state.variantId = design.variantId || null;
  state.visibleCount = THREE.MathUtils.clamp(state.visibleCount, 1, design.layers.length);
  if (state.isolatedLayer !== null) state.isolatedLayer = Math.min(state.isolatedLayer, design.layers.length - 1);
  designGroup = new THREE.Group();
  designGroup.name = design.id + (state.variantId ? `:${state.variantId}` : '');
  panelGroups = design.layers.map(makePanel);
  designGroup.add(...panelGroups);
  makeHardware();
  makeRails();
  scene.add(designGroup);
  populateDesignUI();
  updateModel();
  const hash = state.designId + (state.variantId ? `:${state.variantId}` : '');
  try { history.replaceState(null, '', `#${encodeURIComponent(hash)}`); } catch { /* file:// history is optional. */ }
}

function selectDesign(id, keepView = false, variantId = undefined) {
  const next = resolveDesign(id, variantId);
  if (!next || !renderer) return false;
  state.visibleCount = next.layers.length;
  state.isolatedLayer = null;
  state.explode = 0;
  state.section = false;
  if (!keepView) state.view = 'iso';
  installDesign(next);
  fitCamera(VIEWS[state.view] || VIEWS.iso);
  return true;
}

function setVariant(variantId) {
  const options = variantsFor(state.designId);
  const next = options.find((item) => item.variantId === variantId);
  if (!next || options.length < 2 || !renderer) return false;
  if (next === design) return true;
  // Both variants use the same envelope. Keep the user's exact camera, selected
  // layer, spacing and display switches while changing only the PCB geometry.
  installDesign(next);
  requestRender();
  return true;
}

function setExplode(value) {
  if (!design) return;
  state.explode = THREE.MathUtils.clamp(Number(value) || 0, 0, 12);
  updateModel();
  fitCamera();
}

function setVisibleCount(value) {
  if (!design) return;
  state.visibleCount = THREE.MathUtils.clamp(Math.round(Number(value) || 1), 1, design.layers.length);
  state.isolatedLayer = null;
  updateModel();
  fitCamera();
}

function isolateLayer(index) {
  if (!design) return;
  if (index === null || index === undefined) state.isolatedLayer = null;
  else state.isolatedLayer = THREE.MathUtils.clamp(Math.round(Number(index) || 0), 0, design.layers.length - 1);
  updateModel();
  fitCamera();
}

function reset() {
  if (!design) return;
  state.visibleCount = design.layers.length;
  state.isolatedLayer = null;
  state.explode = 0;
  state.artwork = true;
  state.hardware = true;
  state.rails = false;
  state.section = false;
  state.view = 'iso';
  updateModel();
  setView('iso');
}

async function downloadPNG() {
  if (!renderer || !state.ready) return;
  const button = $('download-png');
  button.disabled = true;
  try {
    const alpha = renderer.getClearAlpha();
    const clear = renderer.getClearColor(new THREE.Color()).clone();
    renderer.setClearColor('#1c1e21', 1);
    renderer.render(scene, camera);
    const blob = await new Promise((resolve, reject) => renderer.domElement.toBlob((result) => result ? resolve(result) : reject(new Error('PNG export failed')), 'image/png'));
    renderer.setClearColor(clear, alpha);
    requestRender();
    const url = URL.createObjectURL(blob);
    const link = el('a');
    link.href = url;
    link.download = `${design.id}${state.variantId ? `-${state.variantId}` : ''}-${state.isolatedLayer === null ? state.view : `layer-${state.isolatedLayer + 1}`}${state.explode > 0 ? '-exploded' : ''}.png`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    showToast('Saved the current view as PNG');
  } catch (error) {
    showToast('Could not save the PNG. Please try again.');
    console.error(error);
    renderer.setClearColor(0x141619, 0);
    requestRender();
  } finally { button.disabled = false; }
}

function setupUI() {
  const nav = $('design-nav');
  for (const item of data.designs) {
    const button = el('button', 'design-tab');
    button.type = 'button';
    button.dataset.design = item.id;
    button.setAttribute('aria-pressed', 'false');
    button.append(el('span', 'tab-number', item.number), el('span', '', item.name));
    button.addEventListener('click', () => {
      if (state.designId !== item.id || state.variantId !== (resolveDesign(item.id)?.variantId || null)) selectDesign(item.id);
      button.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
    });
    nav.append(button);
  }
  $('brand-home').addEventListener('click', (event) => { event.preventDefault(); selectDesign(data.designs[0].id); });
  document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
  $('explode').addEventListener('input', (event) => setExplode(event.target.value));
  $('visible-layers').addEventListener('input', (event) => setVisibleCount(event.target.value));
  $('show-all').addEventListener('click', () => setVisibleCount(design.layers.length));
  for (const key of ['artwork', 'hardware', 'rails', 'section']) {
    $(key).addEventListener('change', (event) => { state[key] = event.target.checked; updateModel(); });
  }
  $('reset').addEventListener('click', reset);
  $('download-png').addEventListener('click', downloadPNG);
}

function setupScene() {
  renderer = new THREE.WebGLRenderer({ canvas: $('preview-canvas'), antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x141619, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.localClippingEnabled = true;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  scene = new THREE.Scene();
  const room = new RoomEnvironment();
  pmrem = new THREE.PMREMGenerator(renderer);
  envTarget = pmrem.fromScene(room, 0.045);
  scene.environment = envTarget.texture;
  scene.environmentIntensity = 0.55;
  room.dispose();
  directionalLight = new THREE.DirectionalLight(0xfff2df, 1.5);
  directionalLight.position.set(-100, 200, 240);
  directionalLight.target.position.set(spec.width / 2, spec.height / 2, -25);
  directionalLight.castShadow = true;
  directionalLight.shadow.mapSize.set(2048, 2048);
  directionalLight.shadow.camera.left = -170;
  directionalLight.shadow.camera.right = 170;
  directionalLight.shadow.camera.top = 180;
  directionalLight.shadow.camera.bottom = -180;
  directionalLight.shadow.camera.near = 1;
  directionalLight.shadow.camera.far = 650;
  directionalLight.shadow.bias = -0.00012;
  directionalLight.shadow.normalBias = 0.025;
  directionalLight.shadow.radius = 2;
  scene.add(directionalLight, directionalLight.target);
  const fill = new THREE.DirectionalLight(0xd6e6ff, 0.6);
  fill.position.set(240, -30, 200);
  scene.add(fill);
  const back = new THREE.DirectionalLight(0xffe6b6, 0.6);
  back.position.set(-40, 60, -180);
  scene.add(back);
  const ambient = new THREE.HemisphereLight(0xf1f2ed, 0x606474, 0.3);
  scene.add(ambient);
  camera = new THREE.PerspectiveCamera(32, 1, 0.3, 4000);
  camera.position.set(240, -80, 300);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.enablePan = true;
  controls.screenSpacePanning = true;
  controls.rotateSpeed = 0.72;
  controls.zoomSpeed = 0.8;
  controls.panSpeed = 0.7;
  controls.touches.ONE = THREE.TOUCH.ROTATE;
  controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
  controls.addEventListener('start', () => {
    if (!programmaticCamera) { state.view = 'free'; updateViewUI(); }
  });
  controls.addEventListener('change', requestRender);
  observer = new ResizeObserver(requestRender);
  observer.observe(viewport);
  renderer.domElement.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    state.ready = false;
    $('error-panel').hidden = false;
    $('error-message').textContent = 'The 3D view stopped. Reload this page to restart it.';
  });
}

function inspectLayer(index) {
  const group = panelGroups[index];
  const layer = design?.layers[index];
  if (!group || !layer) return null;
  const artworkMeshes = [];
  const textures = new Set();
  group.traverse((object) => {
    if (!object.isMesh || object === group.userData.body) return;
    artworkMeshes.push(object);
    for (const mat of Array.isArray(object.material) ? object.material : [object.material]) {
      for (const value of Object.values(mat)) if (value?.isTexture) textures.add(value);
    }
  });
  return {
    index,
    finish: layerFinish(layer),
    surface: layer.surface,
    artworkMeshCount: artworkMeshes.length,
    artworkVisibleCount: artworkMeshes.filter((object) => group.visible && object.visible).length,
    artworkTextureCount: textures.size,
    strokeJoin: group.userData.face?.userData.strokeJoin || null,
    strokeCap: group.userData.face?.userData.strokeCap || null,
    boardMaterialMetalness: group.userData.body.material[0].metalness,
  };
}

globalThis.__PCB_PREVIEW__ = {
  get ready() { return state.ready; },
  selectDesign,
  setVariant,
  getState() {
    return {
      ...state,
      variantLabel: design?.variantLabel || null,
      variants: variantsFor(state.designId).filter((item) => item.variantId).map((item) => ({ id: item.variantId, label: item.variantLabel })),
      cameraPosition: camera?.position.toArray() || null,
      cameraTarget: controls?.target.toArray() || null,
      designid: state.designId,
      layersCount: design?.layers.length || 0,
      layerscount: design?.layers.length || 0,
      visiblecount: state.visibleCount,
      isolated: state.isolatedLayer,
      renderedLayers: panelGroups.filter((panel) => panel.visible).map((panel) => panel.userData.index),
      stackDepth: design?.stackDepth || 0,
      explodedDepth: design ? design.stackDepth + (design.layers.length - 1) * state.explode : 0,
      rendererMemory: renderer ? { ...renderer.info.memory } : null,
      actualHardwareVisible: Boolean(hardwareGroup?.visible),
      layerPositions: panelGroups.map((panel) => panel.position.z),
      renderCalls: renderer?.info.render.calls || 0,
      layerFinishes: design?.layers.map(layerFinish) || [],
      finishSummary: finishSummary(),
    };
  },
  setExplode,
  setVisibleCount,
  isolateLayer,
  setView,
  reset,
  downloadPNG,
  inspectLayer,
};

try {
  if (!spec || !data.designs.length) throw new Error('Preview geometry is missing.');
  setupUI();
  setupScene();
  let hashId = '', hashVariant;
  try { [hashId, hashVariant] = decodeURIComponent(location.hash.slice(1)).split(':'); } catch { /* Ignore an invalid optional hash. */ }
  const query = new URLSearchParams(location.search);
  const queryId = query.get('design');
  const initialId = designMap.has(hashId) ? hashId : designMap.has(queryId) ? queryId : designMap.has(globalThis.PCB_INITIAL_DESIGN) ? globalThis.PCB_INITIAL_DESIGN : data.designs[0].id;
  const initialVariant = hashVariant || (queryId === initialId ? query.get('variant') : undefined) || (globalThis.PCB_INITIAL_DESIGN === initialId ? globalThis.PCB_INITIAL_VARIANT : undefined);
  selectDesign(initialId, false, initialVariant);
  requestRender();
} catch (error) {
  initFailed = true;
  state.ready = false;
  $('loading').hidden = true;
  $('error-panel').hidden = false;
  console.error('PCB preview could not start:', error);
  if (String(error.message).includes('geometry')) $('error-message').textContent = error.message;
}

window.addEventListener('pagehide', (event) => {
  if (event.persisted) return;
  if (renderFrame !== null) cancelAnimationFrame(renderFrame);
  observer?.disconnect();
  controls?.dispose();
  if (renderer) disposeDesign();
  envTarget?.dispose();
  pmrem?.dispose();
  renderer?.dispose();
});
