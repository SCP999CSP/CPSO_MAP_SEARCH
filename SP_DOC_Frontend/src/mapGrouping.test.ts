import { describe, expect, it } from "vitest";
import { markersBySpecialty, slotPosition } from "./mapGrouping";
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
