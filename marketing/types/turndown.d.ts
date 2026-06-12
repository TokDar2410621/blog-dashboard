/**
 * Minimal ambient declaration for `turndown` (HTML -> Markdown converter).
 * The marketing app does not ship @types/turndown, so we declare just the
 * surface the editor uses (constructor options, addRule, turndown).
 */
declare module "turndown" {
  interface TurndownOptions {
    headingStyle?: "setext" | "atx";
    hr?: string;
    bulletListMarker?: "-" | "+" | "*";
    codeBlockStyle?: "indented" | "fenced";
    fence?: "```" | "~~~";
    emDelimiter?: "_" | "*";
    strongDelimiter?: "__" | "**";
    linkStyle?: "inlined" | "referenced";
    linkReferenceStyle?: "full" | "collapsed" | "shortcut";
  }

  type TurndownFilter =
    | string
    | string[]
    | ((node: Node, options: TurndownOptions) => boolean);

  interface TurndownRule {
    filter: TurndownFilter;
    replacement: (
      content: string,
      node: Node,
      options?: TurndownOptions
    ) => string;
  }

  export default class TurndownService {
    constructor(options?: TurndownOptions);
    turndown(html: string | Node): string;
    addRule(key: string, rule: TurndownRule): this;
    keep(filter: TurndownFilter): this;
    remove(filter: TurndownFilter): this;
    use(plugin: unknown): this;
  }
}
