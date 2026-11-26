import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { api, aoSessaoExpirar, lerSessao } from "./api.ts";
import type { Sessao } from "./tipos.ts";

interface ContextoAuth {
  sessao: Sessao | null;
  entrar: (login: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
}

const AuthContext = createContext<ContextoAuth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(() => lerSessao());

  useEffect(() => {
    aoSessaoExpirar(() => setSessao(null));
    return () => aoSessaoExpirar(null);
  }, []);

  async function entrar(login: string, senha: string): Promise<void> {
    setSessao(await api.entrar(login, senha));
  }

  async function sair(): Promise<void> {
    await api.sair();
    setSessao(null);
  }

  return <AuthContext.Provider value={{ sessao, entrar, sair }}>{children}</AuthContext.Provider>;
}

export function useAuth(): ContextoAuth {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error("useAuth precisa estar dentro de AuthProvider.");
  return contexto;
}
