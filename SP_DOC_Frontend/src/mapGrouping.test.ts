import { describe, expect, it } from "vitest";
import { markersBySpecialty, markersForZoom, SPLIT_ZOOM, slotPosition } from "./mapGrouping";
import type { MapLocation } from "./types";

function loc(
  id: string,
  specialties: string | null,
  latitude = 43.65,
  longitude = -79.38
): MapLocation {
  return {
    id,
    cpso_number: id,
    full_name: id,
    specialties,
    gender: null,
    medical_school: null,
    languages_spoken: null,
    graduate_data: null,
    full_address: null,
    city: null,
    province: null,
    postal_code: null,
    phone: null,
    fax: null,
    latitude,
    longitude,
  };
}

describe("markersBySpecialty", () => {
  it("sums doctors of the same specialty and splits the rest into adjacent slots", () => {
    const markers = markersBySpecialty([
      loc("a", "Neurology"),
      loc("b", "Neurology"),
      loc("c", "Dermatology"),
      loc("d", "Neurology | Gastroenterology"),
      loc("e", "Family Medicine"),
    ]);

    expect(markers.map((m) => [m.specialty, m.records.length, m.slot, m.slotCount])).toEqual([
      ["Neurology", 2, 0, 2],
      ["Dermatology", 1, 1, 2],
    ]);
  });

  it("keeps a single specialty on the original point", () => {
    const markers = markersBySpecialty([
      loc("a", "Hematology", 43.65, -79.38),
      loc("b", "Hematology", 43.7, -79.4),
    ]);
    expect(markers).toHaveLength(2);
    expect(markers.every((m) => m.slotCount === 1)).toBe(true);
  });
});

describe("grid clustering by zoom", () => {
  it("merges nearby points while zoomed out and splits them at street zoom", () => {
    const records = [
      loc("a", "Hematology", 43.6501, -79.38),
      loc("b", "Hematology", 43.651, -79.38),
    ];
    const zoomedOut = markersBySpecialty(records, SPLIT_ZOOM - 2);
    const zoomedIn = markersBySpecialty(records, SPLIT_ZOOM);
    expect(zoomedOut).toHaveLength(1);
    expect(zoomedOut[0].records).toHaveLength(2);
    expect(zoomedIn).toHaveLength(2);
  });

  it("shows one total for nearby mixed specialties until the split zoom", () => {
    const records = [
      loc("a", "Neurology", 43.6501, -79.38),
      loc("b", "Dermatology", 43.651, -79.38),
    ];
    const shown = markersForZoom(
      markersBySpecialty(records, SPLIT_ZOOM - 2),
      SPLIT_ZOOM - 2
    );
    expect(shown).toHaveLength(1);
    expect(shown[0].kind).toBe("site");
    if (shown[0].kind !== "site") return;
    expect(shown[0].records).toHaveLength(2);
  });
});

describe("markersForZoom", () => {
  it("collapses different specialties into one point below the split zoom", () => {
    const markers = markersBySpecialty([
      loc("a", "Neurology"),
      loc("b", "Neurology"),
      loc("c", "Dermatology"),
    ]);
    const shown = markersForZoom(markers, SPLIT_ZOOM - 1);
    expect(shown).toHaveLength(1);
    expect(shown[0]).toMatchObject({ kind: "site", records: expect.any(Array) });
    if (shown[0].kind !== "site") return;
    expect(shown[0].records.map((r) => r.id).sort()).toEqual(["a", "b", "c"]);
  });

  it("splits specialties once zoomed in", () => {
    const markers = markersBySpecialty([
      loc("a", "Neurology"),
      loc("c", "Dermatology"),
    ]);
    const shown = markersForZoom(markers, SPLIT_ZOOM);
    expect(shown.map((m) => m.kind)).toEqual(["specialty", "specialty"]);
  });

  it("leaves a single specialty as its own point at any zoom", () => {
    const markers = markersBySpecialty([loc("a", "Hematology")]);
    expect(markersForZoom(markers, SPLIT_ZOOM - 1)[0].kind).toBe("specialty");
  });
});

describe("slotPosition", () => {
  it("does not move a lone marker", () => {
    expect(slotPosition(43.65, -79.38, 0, 1, 16)).toEqual({
      lat: 43.65,
      lng: -79.38,
    });
  });

  it("places mixed specialties on either side of the shared point", () => {
    const left = slotPosition(43.65, -79.38, 0, 2, 17);
    const right = slotPosition(43.65, -79.38, 1, 2, 17);
    expect(left.lat).toBe(43.65);
    expect(left.lng).toBeLessThan(-79.38);
    expect(right.lng).toBeGreaterThan(-79.38);
    expect(left.lng + right.lng).toBeCloseTo(-79.38 * 2, 6);
  });
});
