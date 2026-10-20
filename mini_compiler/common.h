#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>

typedef enum {
    NODE_PROGRAM,
    NODE_DECL,
    NODE_ASSIGN,
    NODE_INT,
    NODE_FLOAT,
    NODE_ID,
    NODE_BINOP,
    NODE_UNARY,
    NODE_BLOCK,
    NODE_IF,
    NODE_WHILE,
    NODE_EMPTY
} NodeKind;

typedef struct ASTNode {
    NodeKind kind;
    char *text;
    double number;
    int is_float;
    int line;
    struct ASTNode *left;
    struct ASTNode *right;
    struct ASTNode *next;
    struct ASTNode *third; /* else branch */
    char *storage;        /* resolved symbol identity for scoped TAC */
    int scope_id;
} ASTNode;

typedef struct { char *text; int line; } NameToken;
typedef struct { double value; int line; } NumberToken;

ASTNode *make_node(NodeKind kind, const char *text, ASTNode *left,
                   ASTNode *right, int line);
ASTNode *make_number(double value, int is_float, int line);
ASTNode *append_node(ASTNode *list, ASTNode *item);
void free_ast(ASTNode *node);
void print_ast_text(ASTNode *node, int depth);
int semantic_analyze(ASTNode *program);
void generate_tac(ASTNode *program, const char *filename);
void optimize_tac(const char *input_file, const char *output_file);
void write_dot(ASTNode *program, const char *filename);
void yyerror(const char *message);

extern ASTNode *root;
extern int yylineno;
extern int syntax_errors;
extern int lexical_errors;

#endif
