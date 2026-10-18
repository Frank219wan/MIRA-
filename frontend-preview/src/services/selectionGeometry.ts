export interface NormalizedPoint {
  x: number;
  y: number;
}

export interface MediaGeometry {
  sourceWidth: number;
  sourceHeight: number;
  viewportWidth: number;
  viewportHeight: number;
  objectFit: "contain" | "cover";
  mirrored?: boolean;
}

interface RenderedMediaRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

const finitePositive = (value: number) => Number.isFinite(value) && value > 0;

export function renderedMediaRect(geometry: MediaGeometry): RenderedMediaRect {
  const { sourceWidth, sourceHeight, viewportWidth, viewportHeight, objectFit } = geometry;
  if (![sourceWidth, sourceHeight, viewportWidth, viewportHeight].every(finitePositive))
    throw new Error("Invalid media geometry");
  const scale = objectFit === "cover"
    ? Math.max(viewportWidth / sourceWidth, viewportHeight / sourceHeight)
    : Math.min(viewportWidth / sourceWidth, viewportHeight / sourceHeight);
  const width = sourceWidth * scale;
  const height = sourceHeight * scale;
  return {
    left: (viewportWidth - width) / 2,
    top: (viewportHeight - height) / 2,
    width,
    height,
  };
}

export function displayPointToRaw(
  point: { x: number; y: number },
  geometry: MediaGeometry,
): NormalizedPoint | null {
  const media = renderedMediaRect(geometry);
  const displayX = geometry.mirrored ? geometry.viewportWidth - point.x : point.x;
  const x = (displayX - media.left) / media.width;
  const y = (point.y - media.top) / media.height;
  if (![x, y].every(Number.isFinite) || x < 0 || x > 1 || y < 0 || y > 1)
    return null;
  return { x, y };
}

export function rawPointToDisplay(
  point: NormalizedPoint,
  geometry: MediaGeometry,
): { x: number; y: number } {
  const media = renderedMediaRect(geometry);
  const rawX = media.left + point.x * media.width;
  return {
    x: geometry.mirrored ? geometry.viewportWidth - rawX : rawX,
    y: media.top + point.y * media.height,
  };
}

function cross(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint) {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

export function convexHull(points: NormalizedPoint[]): NormalizedPoint[] {
  const unique = [...new Map(points
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    .map((point) => [`${point.x}:${point.y}`, point])).values()]
    .sort((a, b) => a.x - b.x || a.y - b.y);
  if (unique.length < 3) return unique;
  const lower: NormalizedPoint[] = [];
  for (const point of unique) {
    while (lower.length >= 2 && cross(lower.at(-2)!, lower.at(-1)!, point) <= 0)
      lower.pop();
    lower.push(point);
  }
  const upper: NormalizedPoint[] = [];
  for (const point of [...unique].reverse()) {
    while (upper.length >= 2 && cross(upper.at(-2)!, upper.at(-1)!, point) <= 0)
      upper.pop();
    upper.push(point);
  }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)];
}

export function pointInPolygon(point: NormalizedPoint, polygon: NormalizedPoint[]) {
  if (polygon.length < 3) return false;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j];
    const intersects =
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x;
    if (intersects) inside = !inside;
  }
  return inside;
}

function orientation(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint) {
  const value = cross(a, b, c);
  return Math.abs(value) < 1e-9 ? 0 : value > 0 ? 1 : -1;
}

function onSegment(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint) {
  return (
    b.x >= Math.min(a.x, c.x) - 1e-9 && b.x <= Math.max(a.x, c.x) + 1e-9 &&
    b.y >= Math.min(a.y, c.y) - 1e-9 && b.y <= Math.max(a.y, c.y) + 1e-9
  );
}

function segmentsIntersect(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint, d: NormalizedPoint) {
  const o1 = orientation(a, b, c), o2 = orientation(a, b, d);
  const o3 = orientation(c, d, a), o4 = orientation(c, d, b);
  if (o1 !== o2 && o3 !== o4) return true;
  return (
    (o1 === 0 && onSegment(a, c, b)) ||
    (o2 === 0 && onSegment(a, d, b)) ||
    (o3 === 0 && onSegment(c, a, d)) ||
    (o4 === 0 && onSegment(c, b, d))
  );
}

export function isSimplePolygon(points: NormalizedPoint[]) {
  if (points.length < 3) return false;
  for (let i = 0; i < points.length; i++) {
    const nextI = (i + 1) % points.length;
    for (let j = i + 1; j < points.length; j++) {
      const nextJ = (j + 1) % points.length;
      if (i === j || nextI === j || nextJ === i) continue;
      if (segmentsIntersect(points[i], points[nextI], points[j], points[nextJ]))
        return false;
    }
  }
  return true;
}

export function polygonArea(points: NormalizedPoint[]) {
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0)) / 2;
}

export function selectionBounds(points: NormalizedPoint[]) {
  const xs = points.map((point) => point.x), ys = points.map((point) => point.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  return {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    width: maxX - minX,
    height: maxY - minY,
    polygon: points.map(({ x, y }) => ({ x, y })),
  };
}

export function ellipsePolygon(
  selection: { x: number; y: number; width: number; height: number },
  count = 16,
): NormalizedPoint[] {
  return Array.from({ length: count }, (_, index) => ({
    x: Math.min(1, Math.max(0, selection.x + (selection.width / 2) * Math.cos((index * 2 * Math.PI) / count))),
    y: Math.min(1, Math.max(0, selection.y + (selection.height / 2) * Math.sin((index * 2 * Math.PI) / count))),
  }));
}
