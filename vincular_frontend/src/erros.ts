function coletar(valor: unknown, saida: string[]): void {
  if (typeof valor === "string") {
    saida.push(valor);
  } else if (Array.isArray(valor)) {
    valor.forEach((item) => coletar(item, saida));
  } else if (valor !== null && typeof valor === "object") {
    Object.values(valor as Record<string, unknown>).forEach((item) => coletar(item, saida));
  }
}

/** Transforma o corpo de erro do Django REST Framework em uma frase legível. */
export function mensagemDeErro(corpo: unknown, padrao: string): string {
  const mensagens: string[] = [];
  coletar(corpo, mensagens);
  const unicas = [...new Set(mensagens.map((m) => m.trim()).filter((m) => m !== ""))];
  return unicas.length > 0 ? unicas.join(" ") : padrao;
}
