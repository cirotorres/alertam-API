import pkg from "../../package.json";

export function AboutPage() {
  return (
    <section className="page-stack">
      <h1>Sobre o AlertaM</h1>
      <p>
        Interface mobile somente leitura para acompanhamento das movimentações
        marítimas do Porto do Pecém.
      </p>
      <p>Versão {pkg.version}</p>
      <p>Dados operacionais recebidos do AlertaM Desktop.</p>
    </section>
  );
}
