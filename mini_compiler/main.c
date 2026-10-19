#include "common.h"
#include <stdio.h>
#include <stdlib.h>

extern FILE *yyin;
extern int yyparse(void);
void write_dot(ASTNode *program, const char *filename);

int main(int argc, char **argv) {
    if (argc > 2) {
        fprintf(stderr, "Usage: %s [input_file]\n", argv[0]);
        return 2;
    }

    if (argc == 2) {
        yyin = fopen(argv[1], "r");
        if (!yyin) { perror(argv[1]); return 2; }
    }

    printf("=== CODEMIND FLEX/YACC LEARNING LAB ===\n");
    int parse_status = yyparse();

    if (argc == 2 && yyin) fclose(yyin);

    if (parse_status != 0 || syntax_errors > 0 || lexical_errors > 0 || !root) {
        fprintf(stderr, "\nCompilation stopped: lexical/syntax errors were found.\n");
        if (root) free_ast(root);
        return 1;
    }

    printf("\n=== AST / PARSE STRUCTURE ===\n");
    print_ast_text(root, 0);
    write_dot(root, "ast.dot");
    printf("Wrote ast.dot. If Graphviz is installed, run: dot -Tpng ast.dot -o ast.png\n");

    printf("\n=== SEMANTIC ANALYSIS ===\n");
    if (!semantic_analyze(root)) {
        fprintf(stderr, "Intermediate code generation skipped because semantic analysis failed.\n");
        free_ast(root);
        return 1;
    }

    generate_tac(root, "tac.txt");
    optimize_tac("tac.txt", "optimized_tac.txt");

    printf("\n=== THREE-ADDRESS CODE ===\n");
    FILE *f = fopen("tac.txt", "r");
    if (f) { char line[512]; while (fgets(line, sizeof(line), f)) fputs(line, stdout); fclose(f); }

    printf("\n=== OPTIMIZED THREE-ADDRESS CODE ===\n");
    f = fopen("optimized_tac.txt", "r");
    if (f) { char line[512]; while (fgets(line, sizeof(line), f)) fputs(line, stdout); fclose(f); }

    printf("\nGenerated files: ast.dot, tac.txt, optimized_tac.txt\n");
    free_ast(root);
    return 0;
}
