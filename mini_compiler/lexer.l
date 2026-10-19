%{
#include "common.h"
#include "y.tab.h"
#include <stdlib.h>
#include <string.h>

FILE *token_trace = NULL;
static int traced(int token, const char *name) {
    if (token_trace) fprintf(token_trace, "%d\t%s\t%s\n", yylineno, name, yytext);
    return token;
}
#define RETURN(token) return traced(token, #token)
%}

%option noyywrap yylineno

DIGIT       [0-9]
ID          [a-zA-Z_][a-zA-Z0-9_]*
FLOATNUM    ({DIGIT}+\.{DIGIT}*|\.{DIGIT}+)([eE][+-]?{DIGIT}+)?

%%

[ \t\r]+                ;
\n                      ;
"//".*                  ;
"/*"([^*]|\*+[^*/])*\*+"/"  ;
"int"                   { RETURN(INT); }
"float"                 { RETURN(FLOAT); }
{FLOATNUM}              { yylval.number = strtod(yytext, NULL); RETURN(FLOATING); }
{DIGIT}+                { yylval.number = strtod(yytext, NULL); RETURN(INTEGER); }
{ID}                    { yylval.str = strdup(yytext); RETURN(IDENTIFIER); }
"+"                     { RETURN(PLUS); }
"-"                     { RETURN(MINUS); }
"*"                     { RETURN(MULTIPLY); }
"/"                     { RETURN(DIVIDE); }
"%"                     { RETURN(MODULO); }
"="                     { RETURN(ASSIGN); }
"("                     { RETURN(LPAREN); }
")"                     { RETURN(RPAREN); }
";"                     { RETURN(SEMICOLON); }
.                       { fprintf(stderr, "Lexical error at line %d: invalid character '%s'\n", yylineno, yytext); lexical_errors++; }

%%
