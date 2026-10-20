#include "common.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef struct Scope { int id, depth; struct Scope *parent; } Scope;
typedef struct Symbol {
    char *name, *type, *storage;
    int scope_id, depth, line;
    struct Symbol *next;
} Symbol;
static Symbol *symbols = NULL;
static Scope *scope = NULL;
static int next_scope, semantic_errors, temp_counter, label_counter;
static FILE *tac_out;

static char *copy_string(const char *s) {
    if (!s) return NULL;
    char *p = malloc(strlen(s) + 1);
    if (!p) { fprintf(stderr,"Out of memory\n"); exit(2); }
    strcpy(p,s); return p;
}

ASTNode *make_node(NodeKind kind, const char *text, ASTNode *left, ASTNode *right, int line) {
    ASTNode *n = calloc(1,sizeof(*n));
    if (!n) { fprintf(stderr,"Out of memory\n"); exit(2); }
    n->kind=kind; n->text=copy_string(text); n->left=left; n->right=right; n->line=line;
    return n;
}
ASTNode *make_number(double value, int is_float, int line) {
    ASTNode *n=make_node(is_float?NODE_FLOAT:NODE_INT,NULL,NULL,NULL,line);
    n->number=value; n->is_float=is_float; return n;
}
ASTNode *append_node(ASTNode *list, ASTNode *item) {
    if (!list) return item;
    ASTNode *tail=list; while(tail->next) tail=tail->next;
    tail->next=item; return list;
}
void free_ast(ASTNode *n) {
    if (!n) return;
    free_ast(n->left); free_ast(n->right); free_ast(n->third); free_ast(n->next);
    free(n->text); free(n->storage); free(n);
}
static const char *kind_name(NodeKind k) {
    switch(k) {
        case NODE_PROGRAM:return "Program"; case NODE_DECL:return "Declaration";
        case NODE_ASSIGN:return "Assignment"; case NODE_INT:return "Integer";
        case NODE_FLOAT:return "Float"; case NODE_ID:return "Identifier";
        case NODE_BINOP:return "Binary Operator"; case NODE_UNARY:return "Unary Operator";
        case NODE_BLOCK:return "Block"; case NODE_IF:return "If";
        case NODE_WHILE:return "While"; case NODE_EMPTY:return "Empty statement";
    } return "Unknown";
}
void print_ast_text(ASTNode *n,int depth) {
    if (!n) return;
    for(int i=0;i<depth;i++) printf("  ");
    printf("%s",kind_name(n->kind));
    if(n->text) printf(" (%s)",n->text);
    if(n->kind==NODE_INT||n->kind==NODE_FLOAT) printf(" (%g)",n->number);
    printf("\n");
    print_ast_text(n->left,depth+1); print_ast_text(n->right,depth+1);
    print_ast_text(n->third,depth+1); print_ast_text(n->next,depth);
}
static Symbol *find_in_scope(const char *name,int id) {
    for(Symbol *s=symbols;s;s=s->next)
        if(s->scope_id==id && strcmp(s->name,name)==0) return s;
    return NULL;
}
static Symbol *find_symbol(const char *name) {
    for(Scope *p=scope;p;p=p->parent) {
        Symbol *s=find_in_scope(name,p->id); if(s) return s;
    } return NULL;
}
static void bind_node(ASTNode *n,Symbol *s) {
    free(n->storage); n->storage=copy_string(s->storage); n->scope_id=s->scope_id;
    n->is_float=strcmp(s->type,"float")==0;
}
static Symbol *add_symbol(ASTNode *n) {
    if(find_in_scope(n->text,scope->id)) {
        fprintf(stderr,"Semantic error at line %d: variable '%s' is already declared in scope %d.\n",n->line,n->text,scope->id);
        semantic_errors++; return NULL;
    }
    Symbol *s=calloc(1,sizeof(*s));
    if(!s) exit(2);
    s->name=copy_string(n->text); s->type=copy_string(n->left->text);
    s->scope_id=scope->id; s->depth=scope->depth; s->line=n->line;
    char name[96];
    if(scope->id) snprintf(name,sizeof(name),"%s@S%d",s->name,scope->id);
    else snprintf(name,sizeof(name),"%s",s->name);
    s->storage=copy_string(name); s->next=symbols; symbols=s; bind_node(n,s);
    return s;
}
static int comparison(const char *op) {
    return strcmp(op,"<")==0||strcmp(op,"<=")==0||strcmp(op,">")==0||strcmp(op,">=")==0||strcmp(op,"==")==0||strcmp(op,"!=")==0;
}
static int logical(ASTNode *n) {
    return (n->kind==NODE_BINOP&&(strcmp(n->text,"&&")==0||strcmp(n->text,"||")==0)) ||
           (n->kind==NODE_UNARY&&strcmp(n->text,"!")==0);
}
static int expr_is_float(ASTNode *n) {
    if(!n) return 0;
    if(n->kind==NODE_FLOAT) return 1;
    if(n->kind==NODE_ID) return n->is_float;
    if(logical(n)||(n->kind==NODE_BINOP&&comparison(n->text))) return 0;
    return expr_is_float(n->left)||expr_is_float(n->right);
}
static int eval_constant(ASTNode *n,double *out,int *is_float) {
    if(!n) return 0;
    if(n->kind==NODE_INT||n->kind==NODE_FLOAT) {
        *out=n->number; *is_float=n->kind==NODE_FLOAT; return 1;
    }
    double a,b; int fa,fb;
    if(n->kind==NODE_UNARY && eval_constant(n->left,&a,&fa)) {
        *out=strcmp(n->text,"-")==0?-a:strcmp(n->text,"!")==0?!a:a;
        *is_float=strcmp(n->text,"!")==0?0:fa; return 1;
    }
    if(n->kind!=NODE_BINOP || !eval_constant(n->left,&a,&fa)) return 0;
    if(strcmp(n->text,"&&")==0 && !a) { *out=0; *is_float=0; return 1; }
    if(strcmp(n->text,"||")==0 && a) { *out=1; *is_float=0; return 1; }
    if(!eval_constant(n->right,&b,&fb)) return 0;
    const char *op=n->text;
    if(strcmp(op,"+")==0) *out=a+b;
    else if(strcmp(op,"-")==0) *out=a-b;
    else if(strcmp(op,"*")==0) *out=a*b;
    else if(strcmp(op,"/")==0 && b!=0) *out=a/b;
    else if(strcmp(op,"%")==0 && b!=0 && !fa && !fb) *out=fmod(a,b);
    else if(strcmp(op,"<")==0) *out=a<b;
    else if(strcmp(op,"<=")==0) *out=a<=b;
    else if(strcmp(op,">")==0) *out=a>b;
    else if(strcmp(op,">=")==0) *out=a>=b;
    else if(strcmp(op,"==")==0) *out=a==b;
    else if(strcmp(op,"!=")==0) *out=a!=b;
    else if(strcmp(op,"&&")==0) *out=a!=0 && b!=0;
    else if(strcmp(op,"||")==0) *out=a!=0 || b!=0;
    else return 0;
    *is_float=(comparison(op)||logical(n))?0:(fa||fb||strcmp(op,"/")==0);
    return isfinite(*out);
}
static void check_expr(ASTNode *n) {
    if(!n) return;
    if(n->kind==NODE_ID) {
        Symbol *s=find_symbol(n->text);
        if(s) bind_node(n,s);
        else { fprintf(stderr,"Semantic error at line %d: variable '%s' is not declared in this scope.\n",n->line,n->text); semantic_errors++; }
    }
    check_expr(n->left); check_expr(n->right);
    if(n->kind==NODE_BINOP && (strcmp(n->text,"/")==0||strcmp(n->text,"%")==0)) {
        if(strcmp(n->text,"%")==0&&(expr_is_float(n->left)||expr_is_float(n->right))) {
            fprintf(stderr,"Semantic error at line %d: modulo requires integer operands.\n",n->line); semantic_errors++;
        }
        double v; int f;
        if(eval_constant(n->right,&v,&f)&&v==0) {
            fprintf(stderr,"Semantic error at line %d: division or modulo by zero.\n",n->line); semantic_errors++;
        }
    }
}
static void check_statements(ASTNode *head);
static void check_statement(ASTNode *n) {
    if(!n) return;
    if(n->kind==NODE_BLOCK) {
        Scope local={++next_scope,scope->depth+1,scope};
        scope=&local; n->scope_id=local.id; check_statements(n->left); scope=local.parent;
    } else if(n->kind==NODE_DECL) {
        Symbol *s=add_symbol(n); check_expr(n->right);
        if(s && n->right && strcmp(s->type,"int")==0 && expr_is_float(n->right))
            fprintf(stderr,"Semantic warning at line %d: assigning a float expression to int '%s'.\n",n->line,n->text);
    } else if(n->kind==NODE_ASSIGN) {
        Symbol *s=find_symbol(n->text);
        if(s) bind_node(n,s);
        else { fprintf(stderr,"Semantic error at line %d: assignment target '%s' is not declared in this scope.\n",n->line,n->text); semantic_errors++; }
        check_expr(n->left);
        if(s && strcmp(s->type,"int")==0 && expr_is_float(n->left))
            fprintf(stderr,"Semantic warning at line %d: assigning a float expression to int '%s'.\n",n->line,n->text);
    } else if(n->kind==NODE_IF || n->kind==NODE_WHILE) {
        check_expr(n->left); check_statement(n->right); check_statement(n->third);
    }
}
static void check_statements(ASTNode *head) { for(ASTNode *n=head;n;n=n->next) check_statement(n); }
int semantic_analyze(ASTNode *program) {
    while(symbols) { Symbol *s=symbols; symbols=s->next; free(s->name); free(s->type); free(s->storage); free(s); }
    semantic_errors=0; next_scope=0; Scope global={0,0,NULL}; scope=&global;
    check_statements(program?program->left:NULL);
    printf("\nSymbol table:\n%-18s %-10s %-8s %-8s %s\n","Variable","Type","Scope","Depth","Storage");
    FILE *table=fopen("symbols.tsv","w");
    for(Symbol *s=symbols;s;s=s->next) {
        printf("%-18s %-10s %-8d %-8d %s\n",s->name,s->type,s->scope_id,s->depth,s->storage);
        if(table) fprintf(table,"%s\t%s\t%d\t%d\t%s\t%d\n",s->name,s->type,s->scope_id,s->depth,s->storage,s->line);
    }
    if(table) fclose(table);
    scope=NULL;
    if(!semantic_errors) printf("Semantic analysis successful.\n");
    else printf("Semantic analysis failed with %d error(s).\n",semantic_errors);
    return semantic_errors==0;
}

/* IR uses resolved storage names, labels, and explicit short-circuit branches. */
static void emit_expr(ASTNode *n,char *result,size_t size);
static int new_label(void) { return ++label_counter; }
static void emit_condition(ASTNode *n,int yes,int no) {
    if(n->kind==NODE_BINOP && strcmp(n->text,"&&")==0) {
        int mid=new_label(); emit_condition(n->left,mid,no); fprintf(tac_out,"L%d:\n",mid); emit_condition(n->right,yes,no);
    } else if(n->kind==NODE_BINOP && strcmp(n->text,"||")==0) {
        int mid=new_label(); emit_condition(n->left,yes,mid); fprintf(tac_out,"L%d:\n",mid); emit_condition(n->right,yes,no);
    } else if(n->kind==NODE_UNARY && strcmp(n->text,"!")==0) emit_condition(n->left,no,yes);
    else {
        char value[160]; emit_expr(n,value,sizeof(value));
        fprintf(tac_out,"ifFalse %s goto L%d\ngoto L%d\n",value,no,yes);
    }
}
static void emit_expr(ASTNode *n,char *result,size_t size) {
    if(!n) { snprintf(result,size,"0"); return; }
    if(n->kind==NODE_ID) snprintf(result,size,"%s",n->storage?n->storage:n->text);
    else if(n->kind==NODE_INT||n->kind==NODE_FLOAT) snprintf(result,size,"%.17g",n->number);
    else if(logical(n)) {
        int t=++temp_counter,yes=new_label(),no=new_label(),end=new_label();
        emit_condition(n,yes,no);
        fprintf(tac_out,"L%d:\n$t%d = 1\ngoto L%d\nL%d:\n$t%d = 0\nL%d:\n",yes,t,end,no,t,end);
        snprintf(result,size,"$t%d",t);
    } else if(n->kind==NODE_UNARY) {
        char a[160]; emit_expr(n->left,a,sizeof(a)); int t=++temp_counter;
        fprintf(tac_out,"$t%d = %s %s\n",t,n->text,a); snprintf(result,size,"$t%d",t);
    } else if(n->kind==NODE_BINOP) {
        char a[160],b[160]; emit_expr(n->left,a,sizeof(a)); emit_expr(n->right,b,sizeof(b)); int t=++temp_counter;
        fprintf(tac_out,"$t%d = %s %s %s\n",t,a,n->text,b); snprintf(result,size,"$t%d",t);
    }
}
static void emit_statements(ASTNode *head);
static void emit_statement(ASTNode *n) {
    if(!n) return;
    if(n->kind==NODE_BLOCK) emit_statements(n->left);
    else if(n->kind==NODE_ASSIGN || (n->kind==NODE_DECL && n->right)) {
        char value[160]; emit_expr(n->kind==NODE_DECL?n->right:n->left,value,sizeof(value));
        fprintf(tac_out,"%s = %s\n",n->storage?n->storage:n->text,value);
    } else if(n->kind==NODE_IF) {
        int yes=new_label(),no=new_label(),end=n->third?new_label():no;
        emit_condition(n->left,yes,no); fprintf(tac_out,"L%d:\n",yes); emit_statement(n->right);
        if(n->third) { fprintf(tac_out,"goto L%d\nL%d:\n",end,no); emit_statement(n->third); }
        fprintf(tac_out,"L%d:\n",end);
    } else if(n->kind==NODE_WHILE) {
        int head=new_label(),body=new_label(),end=new_label();
        fprintf(tac_out,"L%d:\n",head); emit_condition(n->left,body,end);
        fprintf(tac_out,"L%d:\n",body); emit_statement(n->right);
        fprintf(tac_out,"goto L%d\nL%d:\n",head,end);
    }
}
static void emit_statements(ASTNode *head) { for(ASTNode *n=head;n;n=n->next) emit_statement(n); }
void generate_tac(ASTNode *program,const char *filename) {
    temp_counter=0; label_counter=0; tac_out=fopen(filename,"w");
    if(!tac_out) { perror(filename); return; }
    emit_statements(program?program->left:NULL); fclose(tac_out); tac_out=NULL;
}

/* Constant propagation is deliberately local to basic blocks. */
typedef struct ConstEntry { char name[160],value[64]; struct ConstEntry *next; } ConstEntry;
static void clear_constants(ConstEntry **head) { while(*head) { ConstEntry *p=*head; *head=p->next; free(p); } }
static const char *lookup_const(ConstEntry *head,const char *name) {
    for(ConstEntry *p=head;p;p=p->next) if(strcmp(p->name,name)==0) return p->value;
    return NULL;
}
static void remove_const(ConstEntry **head,const char *name) {
    while(*head) { if(strcmp((*head)->name,name)==0) { ConstEntry *p=*head; *head=p->next; free(p); return; } head=&(*head)->next; }
}
static void set_const(ConstEntry **head,const char *name,const char *value) {
    remove_const(head,name); ConstEntry *p=calloc(1,sizeof(*p)); if(!p) exit(2);
    snprintf(p->name,sizeof(p->name),"%s",name); snprintf(p->value,sizeof(p->value),"%s",value); p->next=*head; *head=p;
}
static int parse_number(const char *s,double *v) {
    if(!s||!*s) return 0;
    char *end; *v=strtod(s,&end); return *end=='\0'&&isfinite(*v);
}
static int fold(double x,const char *op,double y,double *out) {
    if(strcmp(op,"+")==0) *out=x+y; else if(strcmp(op,"-")==0) *out=x-y;
    else if(strcmp(op,"*")==0) *out=x*y; else if(strcmp(op,"/")==0&&y!=0) *out=x/y;
    else if(strcmp(op,"%")==0&&y!=0) *out=fmod(x,y);
    else if(strcmp(op,"<")==0) *out=x<y; else if(strcmp(op,"<=")==0) *out=x<=y;
    else if(strcmp(op,">")==0) *out=x>y; else if(strcmp(op,">=")==0) *out=x>=y;
    else if(strcmp(op,"==")==0) *out=x==y; else if(strcmp(op,"!=")==0) *out=x!=y;
    else return 0;
    return isfinite(*out);
}
void optimize_tac(const char *input_file,const char *output_file) {
    FILE *in=fopen(input_file,"r"),*out=fopen(output_file,"w");
    if(!in||!out) { if(in) fclose(in); if(out) fclose(out); perror("TAC"); return; }
    ConstEntry *constants=NULL;
    char line[768],lhs[160],a[160],op[160],b[160],extra[160];
    while(fgets(line,sizeof(line),in)) {
        /* Never carry facts across a label or branch, including loop backedges. */
        if(strncmp(line,"goto ",5)==0||strncmp(line,"ifFalse ",8)==0||strchr(line,':')) {
            fputs(line,out); clear_constants(&constants); continue;
        }
        int count=sscanf(line," %159s = %159s %159s %159s %159s",lhs,a,op,b,extra);
        if(count==2) {
            const char *known=lookup_const(constants,a); char rhs[160];
            snprintf(rhs,sizeof(rhs),"%s",known?known:a); fprintf(out,"%s = %s\n",lhs,rhs);
            double val; if(parse_number(rhs,&val)) set_const(&constants,lhs,rhs); else remove_const(&constants,lhs);
        } else if(count==3 && (strcmp(a,"-")==0||strcmp(a,"+")==0)) {
            const char *known=lookup_const(constants,op); double value;
            if(parse_number(known?known:op,&value)) {
                char v[64]; snprintf(v,sizeof(v),"%.17g",strcmp(a,"-")==0?-value:value);
                fprintf(out,"%s = %s\n",lhs,v); set_const(&constants,lhs,v);
            } else { fputs(line,out); remove_const(&constants,lhs); }
        } else if(count==4) {
            const char *aa=lookup_const(constants,a),*bb=lookup_const(constants,b);
            char av[160],bv[160]; snprintf(av,sizeof(av),"%s",aa?aa:a); snprintf(bv,sizeof(bv),"%s",bb?bb:b);
            double x,y,z;
            if(parse_number(av,&x)&&parse_number(bv,&y)&&fold(x,op,y,&z)) {
                char v[64]; snprintf(v,sizeof(v),"%.17g",z); fprintf(out,"%s = %s\n",lhs,v); set_const(&constants,lhs,v);
            } else if((strcmp(op,"+")==0&&strcmp(bv,"0")==0) ||
                      (strcmp(op,"-")==0&&strcmp(bv,"0")==0) ||
                      (strcmp(op,"*")==0&&strcmp(bv,"1")==0) ||
                      (strcmp(op,"/")==0&&strcmp(bv,"1")==0)) {
                fprintf(out,"%s = %s\n",lhs,av); remove_const(&constants,lhs);
            } else {
                fprintf(out,"%s = %s %s %s\n",lhs,av,op,bv); remove_const(&constants,lhs);
            }
        } else { fputs(line,out); clear_constants(&constants); }
    }
    clear_constants(&constants); fclose(in); fclose(out);
}
