import { useCallback, useEffect, useState } from "react"
import { getAdminUsers, banUser, unbanUser, getAdminList } from "../api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { Users as UsersIcon, ShieldAlert } from "lucide-react"

function isBanned(user) {
  return !!user.banned_until && new Date(user.banned_until) > new Date()
}

export default function AdminUsersPanel() {
  const [users, setUsers]     = useState([])
  const [admins, setAdmins]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")
  const [busyId, setBusyId]   = useState(null)

  const load = useCallback(async () => {
    try {
      const [usersRes, adminsRes] = await Promise.all([getAdminUsers(), getAdminList()])
      setUsers(usersRes.data)
      setAdmins(adminsRes.data)
      setError("")
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load users")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleToggleBan = async user => {
    setBusyId(user.id)
    try {
      await (isBanned(user) ? unbanUser(user.id) : banUser(user.id))
      await load()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Action failed")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 w-full">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <UsersIcon className="w-5 h-5 text-foreground" />
          <h2 className="text-display-sm font-bold text-foreground tracking-tight leading-tight">Users</h2>
        </div>
        <p className="text-body text-muted-foreground leading-relaxed max-w-xl">
          Everyone signed up for this deployment. Banning revokes access immediately without
          deleting their account or data.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-heading">All users ({users.length})</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 overflow-x-auto">
          {loading ? (
            <p className="text-body text-muted-foreground">Loading…</p>
          ) : users.length === 0 ? (
            <p className="text-body text-muted-foreground">No users yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead>Last sign-in</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map(user => {
                  const banned = isBanned(user)
                  return (
                    <TableRow key={user.id}>
                      <TableCell>{user.email}</TableCell>
                      <TableCell className="text-caption text-muted-foreground">
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                      </TableCell>
                      <TableCell className="text-caption text-muted-foreground">
                        {user.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleDateString() : "Never"}
                      </TableCell>
                      <TableCell>
                        {banned
                          ? <Badge variant="outline" className="bg-danger/10 text-danger border-danger/30">Banned</Badge>
                          : <Badge variant="outline" className="bg-success/10 text-success border-success/30">Active</Badge>}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm" variant={banned ? "outline" : "destructive"}
                          disabled={busyId === user.id}
                          onClick={() => handleToggleBan(user)}
                        >
                          {banned ? "Unban" : "Ban"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {admins && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-foreground" />
              <CardTitle className="text-heading">Admin allowlist</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pt-0 flex flex-col gap-2">
            {admins.emails.length === 0 ? (
              <p className="text-body text-muted-foreground">No admins configured.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {admins.emails.map(email => <Badge key={email} variant="outline">{email}</Badge>)}
              </div>
            )}
            <p className="text-caption text-muted-foreground">{admins.note}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
