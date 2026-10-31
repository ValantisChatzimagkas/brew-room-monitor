type RoomGroup<T> = { room: string | null; items: T[] };

/** Groups by location id (not name), rooms sorted by name; items without a location come last. */
export function groupByRoom<T extends { location: { id: number; name: string } | null }>(items: T[]): RoomGroup<T>[] {
  const rooms = new Map<number, RoomGroup<T>>();
  const noRoom: T[] = [];
  for (const item of items) {
    if (!item.location) {
      noRoom.push(item);
      continue;
    }
    const group = rooms.get(item.location.id) ?? { room: item.location.name, items: [] };
    group.items.push(item);
    rooms.set(item.location.id, group);
  }
  const groups = [...rooms.values()].sort((a, b) => (a.room ?? "").localeCompare(b.room ?? "", undefined, { sensitivity: "base" }));
  return noRoom.length > 0 ? [...groups, { room: null, items: noRoom }] : groups;
}
