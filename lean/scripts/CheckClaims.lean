import CellsProofs
import Lean

open Lean in
run_cmd do
  let register ← IO.ofExcept <| Json.parse (← IO.FS.readFile "claims.json")
  let claims ← IO.ofExcept <| register.getObjValAs? (Array Json) "claims"
  let env ← getEnv
  for claim in claims do
    let id ← IO.ofExcept <| claim.getObjValAs? String "id"
    let theorems ← IO.ofExcept do
      let formal ← claim.getObjVal? "formal"
      formal.getObjValAs? (RBMap String String compare) "theorems"
    for (symbol, source) in theorems do
      let name := symbol.toName
      let some (.thmInfo _) := env.find? name
        | throwError "claim {id} refers to an unknown theorem {symbol}"
      let some mod ← findModuleOf? name
        | throwError "cannot locate the module for {symbol}"
      let expected := "lean/" ++ mod.toString.replace "." "/" ++ ".lean"
      unless source == expected do
        throwError "claim {id} lists {symbol} in {source}, but Lean locates it in {expected}"
