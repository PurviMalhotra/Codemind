%{
#include <stdio.h>
#include <stdlib.h>
#include "common.h"

int yylex(void);
extern FILE *yyin;
ASTNode *root = NULL;
int syntax_errors = 0;
int lexical_errors = 0;
%}

%union {
    NameToken name;
    NumberToken literal;
    int line;
    ASTNode *node;
}

%token <name> IDENTIFIER
%token <literal> INTEGER FLOATING
%token <line> INT FLOAT IF ELSE WHILE LBRACE
%token PLUS MINUS MULTIPLY DIVIDE MODULO ASSIGN
%token LT LE GT GE EQ NE AND OR NOT
%token LPAREN RPAREN RBRACE SEMICOLON
%type <node> program statement_list block_item statement block declaration assignment expression initializer

%nonassoc IF_WITHOUT_ELSE
%nonassoc ELSE
%left OR
%left AND
%left EQ NE
%left LT LE GT GE
%left PLUS MINUS
%left MULTIPLY DIVIDE MODULO
%right UMINUS NOT

%%

program
    : statement_list
      { root = make_node(NODE_PROGRAM, "program", $1, NULL, 1); $$ = root; }
    ;

statement_list
    : /* empty */ { $$ = NULL; }
    | statement_list block_item { $$ = append_node($1, $2); }
    | statement_list error SEMICOLON { yyerrok; $$ = $1; }
    ;

block_item
    : declaration { $$ = $1; }
    | statement { $$ = $1; }
    ;

statement
    : assignment SEMICOLON { $$ = $1; }
    | block { $$ = $1; }
    | SEMICOLON { $$ = make_node(NODE_EMPTY, "empty", NULL, NULL, yylineno); }
    | IF LPAREN expression RPAREN statement %prec IF_WITHOUT_ELSE
      { $$ = make_node(NODE_IF, "if", $3, $5, $1); }
    | IF LPAREN expression RPAREN statement ELSE statement
      { $$ = make_node(NODE_IF, "if/else", $3, $5, $1); $$->third = $7; }
    | WHILE LPAREN expression RPAREN statement
      { $$ = make_node(NODE_WHILE, "while", $3, $5, $1); }
    ;

block
    : LBRACE statement_list RBRACE
      { $$ = make_node(NODE_BLOCK, "block", $2, NULL, $1); }
    ;

initializer
    : /* empty */ { $$ = NULL; }
    | ASSIGN expression { $$ = $2; }
    ;

declaration
    : INT IDENTIFIER initializer SEMICOLON
      { $$ = make_node(NODE_DECL, $2.text, make_node(NODE_ID, "int", NULL, NULL, $1), $3, $1); free($2.text); }
    | FLOAT IDENTIFIER initializer SEMICOLON
      { $$ = make_node(NODE_DECL, $2.text, make_node(NODE_ID, "float", NULL, NULL, $1), $3, $1); free($2.text); }
    ;

assignment
    : IDENTIFIER ASSIGN expression
      { $$ = make_node(NODE_ASSIGN, $1.text, $3, NULL, $1.line); free($1.text); }
    ;

expression
    : expression PLUS expression { $$ = make_node(NODE_BINOP, "+", $1, $3, $1->line); }
    | expression MINUS expression { $$ = make_node(NODE_BINOP, "-", $1, $3, $1->line); }
    | expression MULTIPLY expression { $$ = make_node(NODE_BINOP, "*", $1, $3, $1->line); }
    | expression DIVIDE expression { $$ = make_node(NODE_BINOP, "/", $1, $3, $1->line); }
    | expression MODULO expression { $$ = make_node(NODE_BINOP, "%", $1, $3, $1->line); }
    | expression LT expression { $$ = make_node(NODE_BINOP, "<", $1, $3, $1->line); }
    | expression LE expression { $$ = make_node(NODE_BINOP, "<=", $1, $3, $1->line); }
    | expression GT expression { $$ = make_node(NODE_BINOP, ">", $1, $3, $1->line); }
    | expression GE expression { $$ = make_node(NODE_BINOP, ">=", $1, $3, $1->line); }
    | expression EQ expression { $$ = make_node(NODE_BINOP, "==", $1, $3, $1->line); }
    | expression NE expression { $$ = make_node(NODE_BINOP, "!=", $1, $3, $1->line); }
    | expression AND expression { $$ = make_node(NODE_BINOP, "&&", $1, $3, $1->line); }
    | expression OR expression { $$ = make_node(NODE_BINOP, "||", $1, $3, $1->line); }
    | NOT expression { $$ = make_node(NODE_UNARY, "!", $2, NULL, $2->line); }
    | MINUS expression %prec UMINUS { $$ = make_node(NODE_UNARY, "-", $2, NULL, $2->line); }
    | PLUS expression %prec UMINUS { $$ = make_node(NODE_UNARY, "+", $2, NULL, $2->line); }
    | LPAREN expression RPAREN { $$ = $2; }
    | INTEGER { $$ = make_number($1.value, 0, $1.line); }
    | FLOATING { $$ = make_number($1.value, 1, $1.line); }
    | IDENTIFIER { $$ = make_node(NODE_ID, $1.text, NULL, NULL, $1.line); free($1.text); }
    ;

%%

void yyerror(const char *message) {
    fprintf(stderr, "Syntax error near line %d: %s\n", yylineno, message);
    syntax_errors++;
}
