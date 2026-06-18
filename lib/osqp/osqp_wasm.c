#include "osqp.h"
#include <emscripten/emscripten.h>

EMSCRIPTEN_KEEPALIVE
int osqp_solve_csc(int n,
                   int m,
                   int P_nnz,
                   int *P_p,
                   int *P_i,
                   double *P_x,
                   int A_nnz,
                   int *A_p,
                   int *A_i,
                   double *A_x,
                   double *q,
                   double *l,
                   double *u,
                   double eps_abs,
                   double eps_rel,
                   int max_iter,
                   double rho,
                   double sigma,
                   double *x_out) {
  OSQPCscMatrix *P = OSQPCscMatrix_new(n, n, P_nnz, (OSQPFloat *)P_x, (OSQPInt *)P_i, (OSQPInt *)P_p);
  OSQPCscMatrix *A = OSQPCscMatrix_new(m, n, A_nnz, (OSQPFloat *)A_x, (OSQPInt *)A_i, (OSQPInt *)A_p);
  if (!P || !A) return -10;

  OSQPSettings *settings = OSQPSettings_new();
  if (!settings) return -12;
  settings->verbose = 0;
  settings->eps_abs = eps_abs;
  settings->eps_rel = eps_rel;
  settings->max_iter = max_iter;
  settings->rho = rho;
  settings->sigma = sigma;

  OSQPSolver *solver = OSQP_NULL;
  OSQPInt status = osqp_setup(&solver,
                              P,
                              (const OSQPFloat *)q,
                              A,
                              (const OSQPFloat *)l,
                              (const OSQPFloat *)u,
                              m,
                              n,
                              settings);
  if (status != 0 || !solver) {
    OSQPSettings_free(settings);
    OSQPCscMatrix_free(P);
    OSQPCscMatrix_free(A);
    return (int)status;
  }

  osqp_solve(solver);

  int st = -1;
  if (solver->info) st = (int)solver->info->status_val;

  if (solver->solution && solver->solution->x && x_out) {
    for (int i = 0; i < n; i++) {
      x_out[i] = solver->solution->x[i];
    }
  }

  osqp_cleanup(solver);
  OSQPSettings_free(settings);
  OSQPCscMatrix_free(P);
  OSQPCscMatrix_free(A);
  return st;
}
