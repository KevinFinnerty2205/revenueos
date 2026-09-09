const legacyDefaultPipelineName = "RevenueOS Sales Pipeline";

export function displayPipelineName(name: string): string {
  return name === legacyDefaultPipelineName ? "Oryntela Sales Pipeline" : name;
}
