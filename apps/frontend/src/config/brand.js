/**
 * Configuração de marca — único lugar no frontend onde APP_NAME e contatos da marca são definidos.
 *
 * Em todo o restante do código: importe destas constantes.
 * Nunca escreva o nome literal do produto diretamente em componentes.
 */
export const APP_NAME = import.meta.env.VITE_APP_NAME || "Spirit Blossom";
export const MODERATION_EMAIL =
  import.meta.env.VITE_MODERATION_EMAIL || "moderacao@spirit.blossom";

