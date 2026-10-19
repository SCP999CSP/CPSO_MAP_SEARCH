import { describe, expect, it } from "vitest";
import {
  doctorCategory,
  isListedSpecialty,
  matchSpecialties,
} from "./specialty";

describe("matchSpecialties", () => {
  it("only keeps the five keywords, in fixed order", () => {
    expect(
      matchSpecialties("Rheumatology | Family Medicine | Hematology")
    ).toEqual(["Hematology", "Rheumatology"]);
  });

  it("is case-insensitive", () => {
    expect(matchSpecialties("dermatology")).toEqual(["Dermatology"]);
  });

  it("returns nothing for empty or unrelated specialties", () => {
    expect(matchSpecialties(null)).toEqual([]);
    expect(matchSpecialties("Family Medicine")).toEqual([]);
  });
});

describe("doctorCategory", () => {
  it("ignores non-keyword specialties when deciding single vs multi", () => {
    expect(doctorCategory("Family Medicine | Neurology")).toBe("Neurology");
  });

  it("is multi only when two or more keywords match", () => {
    expect(doctorCategory("Neurology | Gastroenterology")).toBe("multi");
  });

  it("is none when no keyword matches", () => {
    expect(doctorCategory("Family Medicine")).toBe("none");
    expect(doctorCategory(null)).toBe("none");
  });
});

describe("isListedSpecialty", () => {
  it("keeps a single keyword specialty", () => {
    expect(isListedSpecialty("Neurology")).toBe(true);
  });

  it("drops multi and unclassified", () => {
    expect(isListedSpecialty("multi")).toBe(false);
    expect(isListedSpecialty("none")).toBe(false);
  });
});
