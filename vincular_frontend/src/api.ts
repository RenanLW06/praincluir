import { mensagemDeErro } from "./erros.ts";
import type {
  ChamadaDia, DiaTurma, Pagina, RegistroChamada, Sessao, Turma,
} from "./tipos.ts";

// Em desenvolvimento, "/api" é repassado ao Django pelo Vite (veja vite.config.ts).
// Em produção, defina VITE_API_URL com o endereço completo da API.
const BASE: string = import.meta.env.VITE_API_URL ?? "/api";

// A sessão fica em sessionStorage: some quando a aba/janela é fechada.
// É mais seguro para computadores compartilhados, pois há dados de crianças.
const CHAVE_SESSAO = "vincular.sessao";

export function lerSessao(): Sessao | null {
  try {
    const bruto = sessionStorage.getItem(CHAVE_SESSAO);
    return bruto ? (JSON.parse(bruto) as Sessao) : null;
  } catch {
    return null;
  }
}

function salvarSessao(sessao: Sessao): void {
  sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
}

function limparSessao(): void {
  sessionStorage.removeItem(CHAVE_SESSAO);
}

let aoExpirar: (() => void) | null = null;

/** Registra o que fazer quando o servidor disser que a sessão não vale mais. */
export function aoSessaoExpirar(acao: (() => void) | null): void {
  aoExpirar = acao;
}

export class ErroApi extends Error {
  status: number;

  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
  }
}

export function textoDoErro(erro: unknown): string {
  return erro instanceof ErroApi ? erro.message : "Algo deu errado. Tente novamente.";
}

interface Opcoes {
  metodo?: "GET" | "POST";
  corpo?: unknown;
  autenticada?: boolean;
}

async function requisicao<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const { metodo = "GET", corpo, autenticada = true } = opcoes;
  const cabecalhos: Record<string, string> = { Accept: "application/json" };
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  const sessao = lerSessao();
  if (autenticada && sessao) cabecalhos["Authorization"] = `Token ${sessao.token}`;

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroApi("Não foi possível falar com o servidor. Confira se a API está ligada.", 0);
  }

  if (resposta.status === 401 && autenticada) {
    limparSessao();
    aoExpirar?.();
    throw new ErroApi("Sua sessão expirou. Entre novamente.", 401);
  }

  const texto = await resposta.text();
  let dados: unknown = null;
  if (texto) {
    try {
      dados = JSON.parse(texto);
    } catch {
      dados = null;
    }
  }
  if (!resposta.ok) {
    throw new ErroApi(mensagemDeErro(dados, `Erro ${resposta.status} no servidor.`), resposta.status);
  }
  return dados as T;
}

export const api = {
  async entrar(login: string, senha: string): Promise<Sessao> {
    const sessao = await requisicao<Sessao>("/auth/login/", {
      metodo: "POST",
      corpo: { login, senha },
      autenticada: false,
    });
    salvarSessao(sessao);
    return sessao;
  },

  async sair(): Promise<void> {
    try {
      await requisicao<null>("/auth/logout/", { metodo: "POST" });
    } catch {
      // mesmo que o servidor não responda, a sessão local é encerrada
    }
    limparSessao();
  },

  diasTurma(): Promise<DiaTurma[]> {
    return requisicao<DiaTurma[]>("/dias-turma/");
  },

  async turmas(): Promise<Turma[]> {
    const pagina = await requisicao<Pagina<Turma>>("/turmas/?page_size=500");
    return pagina.results;
  },

  chamada(turmaId: number, data: string): Promise<ChamadaDia> {
    return requisicao<ChamadaDia>(`/turmas/${turmaId}/chamada/?data=${data}`);
  },

  salvarChamada(turmaId: number, data: string, registros: RegistroChamada[]): Promise<ChamadaDia> {
    return requisicao<ChamadaDia>(`/turmas/${turmaId}/chamada/`, {
      metodo: "POST",
      corpo: { data, registros },
    });
  },
};
