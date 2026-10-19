#include "common.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

typedef struct Symbol {
    char *name;
    char *type;
    int has_value;
    double value;
    int value_is_float;
    struct Symbol *next;
} Symbol;

static Symbol *symbols = NULL;
static int semantic_errors = 0;
static int temp_counter = 0;
static FILE *tac_out = NULL;

static char *copy_string(const char *s) {
    if (!s) return NULL;
    char *p = (char *)malloc(strlen(s) + 1);
    if (p) strcpy(p, s);
    return p;
}

ASTNode *make_node(NodeKind kind, const char *text, ASTNode *left,
                   ASTNode *right, int line) {
    ASTNode *n = (ASTNode *)calloc(1, sizeof(ASTNode));
    if (!n) {
        fprintf(stderr, "Fatal error: out of memory\n");
        exit(EXIT_FAILURE);
    }
    n->kind = kind;
    n->text = copy_string(text);
    n->left = left;
    n->right = right;
    n->line = line;
    return n;
}

ASTNode *make_number(double value, int is_float, int line) {
    ASTNode *n = make_node(is_float ? NODE_FLOAT : NODE_INT, NULL, NULL, NULL, line);
    n->number = value;
    n->is_float = is_float;
    return n;
}

ASTNode *append_node(ASTNode *list, ASTNode *item) {
    if (!list) return item;
    ASTNode *tail = list;
    while (tail->next) tail = tail->next;
    tail->next = item;
    return list;
}

void free_ast(ASTNode *node) {
    if (!node) return;
    free_ast(node->left);
    free_ast(node->right);
    free_ast(node->next);
    free(node->text);
    free(node);
}

static const char *kind_name(NodeKind kind) {
    switch (kind) {
        case NODE_PROGRAM: return "Program";
        case NODE_DECL: return "Declaration";
        case NODE_ASSIGN: return "Assignment";
        case NODE_INT: return "Integer";
        case NODE_FLOAT: return "Float";
        case NODE_ID: return "Identifier";
        case NODE_BINOP: return "Binary Operator";
        case NODE_UNARY: return "Unary Operator";
    }
    return "Unknown";
}

void print_ast_text(ASTNode *node, int depth) {
    if (!node) return;
    for (int i = 0; i < depth; ++i) printf("  ");
    printf("%s", kind_name(node->kind));
    if (node->text) printf(" (%s)", node->text);
    if (node->kind == NODE_INT) printf(" (%.0f)", node->number);
    if (node->kind == NODE_FLOAT) printf(" (%g)", node->number);
    printf("\n");
    print_ast_text(node->left, depth + 1);
    print_ast_text(node->right, depth + 1);
    print_ast_text(node->next, depth);
}

static Symbol *find_symbol(const char *name) {
    for (Symbol *s = symbols; s; s = s->next)
        if (strcmp(s->name, name) == 0) return s;
    return NULL;
}

static void add_symbol(const char *name, const char *type, int line) {
    if (find_symbol(name)) {
        fprintf(stderr, "Semantic error at line %d: variable '%s' is already declared.\n",
                line, name);
        semantic_errors++;
        return;
    }
    Symbol *s = (Symbol *)calloc(1, sizeof(Symbol));
    s->name = copy_string(name);
    s->type = copy_string(type);
    s->next = symbols;
    symbols = s;
}

static int expr_is_float(ASTNode *n) {
    if (!n) return 0;
    if (n->kind == NODE_FLOAT) return 1;
    if (n->kind == NODE_ID) {
        Symbol *s = find_symbol(n->text);
        return s && strcmp(s->type, "float") == 0;
    }
    return expr_is_float(n->left) || expr_is_float(n->right);
}

static int eval_constant(ASTNode *n, double *out, int *is_float) {
    if (!n) return 0;
    if (n->kind == NODE_INT || n->kind == NODE_FLOAT) {
        *out = n->number;
        *is_float = n->kind == NODE_FLOAT;
        return 1;
    }
    if (n->kind == NODE_UNARY) {
        double v; int f;
        if (!eval_constant(n->left, &v, &f)) return 0;
        if (strcmp(n->text, "-") == 0) v = -v;
        *out = v; *is_float = f;
        return 1;
    }
    if (n->kind == NODE_BINOP) {
        double a, b; int fa, fb;
        if (!eval_constant(n->left, &a, &fa) ||
            !eval_constant(n->right, &b, &fb)) return 0;
        if (strcmp(n->text, "+") == 0) *out = a + b;
        else if (strcmp(n->text, "-") == 0) *out = a - b;
        else if (strcmp(n->text, "*") == 0) *out = a * b;
        else if (strcmp(n->text, "/") == 0) {
            if (fabs(b) < 1e-12) return 0;
            *out = a / b;
        } else if (strcmp(n->text, "%") == 0) {
            if (fabs(b) < 1e-12) return 0;
            if (fa || fb) return 0;
            *out = fmod(a, b);
        } else return 0;
        *is_float = fa || fb || strcmp(n->text, "/") == 0;
        return 1;
    }
    return 0;
}

static void check_expr(ASTNode *n) {
    if (!n) return;
    if (n->kind == NODE_ID && !find_symbol(n->text)) {
        fprintf(stderr, "Semantic error at line %d: variable '%s' is not declared.\n",
                n->line, n->text);
        semantic_errors++;
    }
    check_expr(n->left);
    check_expr(n->right);
    if (n->kind == NODE_BINOP && strcmp(n->text, "/") == 0) {
        double v; int f;
        if (eval_constant(n->right, &v, &f) && fabs(v) < 1e-12) {
            fprintf(stderr, "Semantic error at line %d: division by zero.\n", n->line);
            semantic_errors++;
        }
    }
    if (n->kind == NODE_BINOP && strcmp(n->text, "%") == 0) {
        if (expr_is_float(n->left) || expr_is_float(n->right)) {
            fprintf(stderr, "Semantic error at line %d: modulo requires integer operands.\n", n->line);
            semantic_errors++;
        }
        double v; int f;
        if (eval_constant(n->right, &v, &f) && fabs(v) < 1e-12) {
            fprintf(stderr, "Semantic error at line %d: modulo by zero.\n", n->line);
            semantic_errors++;
        }
    }
}

int semantic_analyze(ASTNode *program) {
    symbols = NULL;
    semantic_errors = 0;

    for (ASTNode *s = program ? program->left : NULL; s; s = s->next) {
        if (s->kind == NODE_DECL) add_symbol(s->text, s->left ? s->left->text : "int", s->line);
        if (s->kind == NODE_ASSIGN) {
            Symbol *target = find_symbol(s->text);
            if (!target) {
                fprintf(stderr, "Semantic error at line %d: assignment target '%s' is not declared.\n",
                        s->line, s->text);
                semantic_errors++;
            }
            check_expr(s->left);
            if (target && target->type && strcmp(target->type, "int") == 0 && expr_is_float(s->left)) {
                fprintf(stderr, "Semantic warning at line %d: assigning a float expression to int '%s'.\n",
                        s->line, s->text);
            }
        }
    }

    printf("\nSymbol table:\n");
    printf("%-18s %-10s\n", "Variable", "Type");
    printf("------------------------------\n");
    for (Symbol *s = symbols; s; s = s->next)
        printf("%-18s %-10s\n", s->name, s->type);

    if (semantic_errors == 0) printf("Semantic analysis successful.\n");
    else printf("Semantic analysis failed with %d error(s).\n", semantic_errors);
    return semantic_errors == 0;
}

static char *new_temp(void) {
    char buf[32];
    snprintf(buf, sizeof(buf), "$t%d", ++temp_counter);
    return copy_string(buf);
}

static void emit_expr(ASTNode *n, char *result, size_t result_size) {
    if (!n) { snprintf(result, result_size, "<?>"); return; }
    if (n->kind == NODE_ID) snprintf(result, result_size, "%s", n->text);
    else if (n->kind == NODE_INT) snprintf(result, result_size, "%.0f", n->number);
    else if (n->kind == NODE_FLOAT) snprintf(result, result_size, "%g", n->number);
    else if (n->kind == NODE_UNARY) {
        char operand[128];
        emit_expr(n->left, operand, sizeof(operand));
        char *t = new_temp();
        fprintf(tac_out, "%s = %s%s\n", t, n->text, operand);
        snprintf(result, result_size, "%s", t);
        free(t);
    } else if (n->kind == NODE_BINOP) {
        char a[128], b[128];
        emit_expr(n->left, a, sizeof(a));
        emit_expr(n->right, b, sizeof(b));
        char *t = new_temp();
        fprintf(tac_out, "%s = %s %s %s\n", t, a, n->text, b);
        snprintf(result, result_size, "%s", t);
        free(t);
    }
}

void generate_tac(ASTNode *program, const char *filename) {
    temp_counter = 0;
    tac_out = fopen(filename, "w");
    if (!tac_out) { perror(filename); return; }
    for (ASTNode *s = program ? program->left : NULL; s; s = s->next) {
        if (s->kind == NODE_ASSIGN) {
            char value[128];
            emit_expr(s->left, value, sizeof(value));
            fprintf(tac_out, "%s = %s\n", s->text, value);
        }
    }
    fclose(tac_out);
    tac_out = NULL;
}

static int is_identifier(const char *s) {
    if (!s || !(isalpha((unsigned char)s[0]) || s[0] == '_')) return 0;
    for (int i = 1; s[i]; ++i)
        if (!(isalnum((unsigned char)s[i]) || s[i] == '_')) return 0;
    return 1;
}

static int parse_number(const char *s, double *v) {
    if (!s || !*s) return 0;
    char *end;
    *v = strtod(s, &end);
    return *end == '\0';
}

typedef struct ConstEntry {
    char name[64];
    char value[64];
    struct ConstEntry *next;
} ConstEntry;

static const char *lookup_const(ConstEntry *head, const char *name) {
    for (ConstEntry *p = head; p; p = p->next)
        if (strcmp(p->name, name) == 0) return p->value;
    return NULL;
}

static void set_const(ConstEntry **head, const char *name, const char *value) {
    ConstEntry *p = *head;
    while (p) {
        if (strcmp(p->name, name) == 0) {
            snprintf(p->value, sizeof(p->value), "%s", value);
            return;
        }
        p = p->next;
    }
    p = (ConstEntry *)calloc(1, sizeof(ConstEntry));
    snprintf(p->name, sizeof(p->name), "%s", name);
    snprintf(p->value, sizeof(p->value), "%s", value);
    p->next = *head;
    *head = p;
}

static void remove_const(ConstEntry **head, const char *name) {
    ConstEntry **p = head;
    while (*p) {
        if (strcmp((*p)->name, name) == 0) {
            ConstEntry *dead = *p;
            *p = dead->next;
            free(dead);
            return;
        }
        p = &(*p)->next;
    }
}

static int is_temp_name(const char *s) {
    return s && s[0] == 't' && isdigit((unsigned char)s[1]);
}

void optimize_tac(const char *input_file, const char *output_file) {
    FILE *in = fopen(input_file, "r");
    FILE *out = fopen(output_file, "w");
    if (!in || !out) {
        if (in) fclose(in);
        if (out) fclose(out);
        perror("Could not open TAC files");
        return;
    }

    ConstEntry *constants = NULL;
    char line[512], lhs[128], a[128], op[8], b[128], extra[128];
    while (fgets(line, sizeof(line), in)) {
        lhs[0] = a[0] = op[0] = b[0] = extra[0] = '\0';
        int count = sscanf(line, " %127s = %127s %7s %127s %127s", lhs, a, op, b, extra);

        if (count == 2) {
            const char *known = lookup_const(constants, a);
            const char *rhs = known ? known : a;
            fprintf(out, "%s = %s\n", lhs, rhs);
            double val;
            if (parse_number(rhs, &val)) set_const(&constants, lhs, rhs);
            else remove_const(&constants, lhs);
        } else if (count == 4) {
            const char *aa = lookup_const(constants, a);
            const char *bb = lookup_const(constants, b);
            const char *av = aa ? aa : a;
            const char *bv = bb ? bb : b;
            double x, y, z;
            int nx = parse_number(av, &x), ny = parse_number(bv, &y);
            int folded = nx && ny;
            if (folded) {
                if (strcmp(op, "+") == 0) z = x + y;
                else if (strcmp(op, "-") == 0) z = x - y;
                else if (strcmp(op, "*") == 0) z = x * y;
                else if (strcmp(op, "/") == 0 && fabs(y) > 1e-12) z = x / y;
                else if (strcmp(op, "%") == 0 && fabs(y) > 1e-12) z = fmod(x, y);
                else folded = 0;
            }
            if (folded) {
                char value[64];
                if (fabs(z - round(z)) < 1e-9) snprintf(value, sizeof(value), "%.0f", z);
                else snprintf(value, sizeof(value), "%.8g", z);
                fprintf(out, "%s = %s\n", lhs, value);
                set_const(&constants, lhs, value);
            } else {
                if (strcmp(op, "+") == 0 && strcmp(bv, "0") == 0) {
                    fprintf(out, "%s = %s\n", lhs, av);
                    if (aa) set_const(&constants, lhs, aa); else remove_const(&constants, lhs);
                } else if (strcmp(op, "*") == 0 && strcmp(bv, "1") == 0) {
                    fprintf(out, "%s = %s\n", lhs, av);
                    if (aa) set_const(&constants, lhs, aa); else remove_const(&constants, lhs);
                } else if (strcmp(op, "*") == 0 && strcmp(bv, "0") == 0) {
                    fprintf(out, "%s = 0\n", lhs);
                    set_const(&constants, lhs, "0");
                } else {
                    fprintf(out, "%s = %s %s %s\n", lhs, av, op, bv);
                    remove_const(&constants, lhs);
                }
            }
        } else {
            fputs(line, out);
        }
    }

    while (constants) {
        ConstEntry *next = constants->next;
        free(constants);
        constants = next;
    }
    fclose(in);
    fclose(out);
}
