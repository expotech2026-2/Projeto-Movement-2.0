export const AC_KINDS = {
  split: "Split",
  janela: "Janela",
  cassete: "Cassete",
  piso_teto: "Piso-teto",
  portatil: "Portátil",
  vrf: "VRF / VRV",
};
export const AC_STATUS = {
  ativo: "Em operação",
  manutencao: "Em manutenção",
  inativo: "Inativo",
};
// Tipos cobertos pela tabela PBE do Inmetro; portátil e VRF ficam fora dela.
export const CATALOG_KINDS = ["split", "janela", "cassete", "piso_teto"];
export const AC_FUNCTIONS = { frio: "Só frio", quente_frio: "Quente/frio" };
export const ROLES = { admin: "Administrador", professor: "Professor" };
