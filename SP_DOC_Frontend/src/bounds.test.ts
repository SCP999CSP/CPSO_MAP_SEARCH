import { describe, expect, it } from "vitest";
import { boundsKey, fromLatLngBounds, roundBounds, toQueryString } from "./bounds";

const TORONTO = { north: 43.86, south: 43.58, east: -79.11, west: -79.64 };

function fakeLatLngBounds(b: typeof TORONTO): google.maps.LatLngBounds {
  return {
    getNorthEast: () => ({ lat: () => b.north, lng: () => b.east }),
    getSouthWest: () => ({ lat: () => b.south, lng: () => b.west }),
  } as unknown as google.maps.LatLngBounds;
}

describe("boundsKey", () => {
  it("treats sub-meter jitter as the same bounds", () => {
    const jittered = {
      north: 43.860001,
      south: 43.579999,
      east: -79.110002,
      west: -79.640003,
    };
    expect(boundsKey(jittered)).toBe(boundsKey(TORONTO));
  });

  it("changes when the map actually moves", () => {
    const moved = { ...TORONTO, north: 43.87 };
    expect(boundsKey(moved)).not.toBe(boundsKey(TORONTO));
  });
});

describe("fromLatLngBounds", () => {
  it("maps corners to north/south/east/west and rounds them", () => {
    const b = fromLatLngBounds(
      fakeLatLngBounds({ ...TORONTO, north: 43.8612345678 })
    );
    expect(b).toEqual({ ...TORONTO, north: 43.86123 });
  });
});

describe("toQueryString", () => {
  it("encodes all four edges", () => {
    const params = new URLSearchParams(toQueryString(roundBounds(TORONTO)));
    expect(Object.fromEntries(params)).toEqual({
      north: "43.86",
      south: "43.58",
      east: "-79.11",
      west: "-79.64",
    });
  });
});
