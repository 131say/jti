/** Сборка Blueprint v4.3 с ``generators.gearbox`` и параметрами в ``global_variables``. */

export type GearboxPresetOptions = {
  ratio: number;
  module: number;
  thickness: number;
  bore: number;
  highLod?: boolean;
  projectId?: string;
};

export function buildGearboxBlueprintJson(opts: GearboxPresetOptions): string {
  const {
    ratio,
    module,
    thickness,
    bore,
    highLod = false,
    projectId = "gearbox_generated",
  } = opts;
  const o = {
    metadata: { project_id: projectId, schema_version: "4.3" },
    global_variables: {
      gearbox_ratio: ratio,
      gearbox_module: module,
      gear_thickness: thickness,
      gear_bore: bore,
    },
    global_settings: { units: "mm", up_axis: "Z" },
    geometry: { parts: [] as unknown[] },
    simulation: {
      materials: [
        { mat_id: "steel", density: 7850, friction: 0.42 },
      ],
      nodes: [] as unknown[],
      joints: [] as unknown[],
    },
    generators: [
      {
        type: "gearbox",
        ratio: "$gearbox_ratio",
        module: "$gearbox_module",
        thickness: "$gear_thickness",
        bore_diameter: "$gear_bore",
        center_distance: "auto",
        high_lod: highLod,
      },
    ],
  };
  return JSON.stringify(o, null, 2);
}
