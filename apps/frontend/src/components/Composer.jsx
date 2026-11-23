/**
 * Composer.jsx — mantido para compatibilidade com testes legados.
 *
 * O componente ativo é PostComposer.jsx (design flat, sem card-dentro-de-card).
 * Re-exporta PostComposer como { Composer } para que todos os imports existentes
 * continuem funcionando sem alteração.
 */
export { PostComposer as Composer } from "./PostComposer";
