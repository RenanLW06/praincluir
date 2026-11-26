import { useAuth } from "./AuthContext.tsx";
import Login from "./Login.tsx";
import TelaChamada from "./TelaChamada.tsx";

export default function App() {
  const { sessao, sair } = useAuth();

  if (!sessao) return <Login />;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <span className="text-lg font-bold text-blue-700">Vincular</span>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-right text-slate-600">
              {sessao.usuario.nome}
              <span className="block text-xs text-slate-400">
                {sessao.usuario.perfil === "administrador" ? "Administrador" : "Monitor"}
              </span>
            </span>
            <button
              onClick={() => void sair()}
              className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-100"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-5">
        <TelaChamada />
      </main>
    </div>
  );
}
