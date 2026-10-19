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
    char *str;
    double number;
    ASTNode *node;
}

%token <str> IDENTIFIER
%token <number> INTEGER FLOATING
%token INT FLOAT
%token PLUS MINUS MULTIPLY DIVIDE MODULO ASSIGN
%token LPAREN RPAREN SEMICOLON
%type <node> program statement_list statement declaration assignment expression

%left PLUS MINUS
%left MULTIPLY DIVIDE MODULO
%right UMINUS

%%

program
    : statement_list
      {
          root = make_node(NODE_PROGRAM, "program", $1, NULL, yylineno);
          $$ = root;
      }
    ;

statement_list
    : /* empty */
      { $$ = NULL; }
    | statement_list statement
      { $$ = append_node($1, $2); }
    | statement_list error SEMICOLON
      {
          yyerrok;
          $$ = $1;
      }
    ;

statement
    : declaration
      { $$ = $1; }
    | assignment SEMICOLON
      { $$ = $1; }
    ;

declaration
    : INT IDENTIFIER SEMICOLON
      {
          ASTNode *type = make_node(NODE_ID, "int", NULL, NULL, yylineno);
          $$ = make_node(NODE_DECL, $2, type, NULL, yylineno);
          free($2);
      }
    | FLOAT IDENTIFIER SEMICOLON
      {
          ASTNode *type = make_node(NODE_ID, "float", NULL, NULL, yylineno);
          $$ = make_node(NODE_DECL, $2, type, NULL, yylineno);
          free($2);
      }
    ;

assignment
    : IDENTIFIER ASSIGN expression
      {
          $$ = make_node(NODE_ASSIGN, $1, $3, NULL, yylineno);
          free($1);
      }
    ;

expression
    : expression PLUS expression
      { $$ = make_node(NODE_BINOP, "+", $1, $3, yylineno); }
    | expression MINUS expression
      { $$ = make_node(NODE_BINOP, "-", $1, $3, yylineno); }
    | expression MULTIPLY expression
      { $$ = make_node(NODE_BINOP, "*", $1, $3, yylineno); }
    | expression DIVIDE expression
      { $$ = make_node(NODE_BINOP, "/", $1, $3, yylineno); }
    | expression MODULO expression
      { $$ = make_node(NODE_BINOP, "%", $1, $3, yylineno); }
    | MINUS expression %prec UMINUS
      { $$ = make_node(NODE_UNARY, "-", $2, NULL, yylineno); }
    | PLUS expression %prec UMINUS
      { $$ = make_node(NODE_UNARY, "+", $2, NULL, yylineno); }
    | LPAREN expression RPAREN
      { $$ = $2; }
    | INTEGER
      { $$ = make_number($1, 0, yylineno); }
    | FLOATING
      { $$ = make_number($1, 1, yylineno); }
    | IDENTIFIER
      {
          $$ = make_node(NODE_ID, $1, NULL, NULL, yylineno);
          free($1);
      }
    ;

%%

void yyerror(const char *message)
{
    fprintf(stderr, "Syntax error near line %d: %s\n", yylineno, message);
    syntax_errors++;
}
